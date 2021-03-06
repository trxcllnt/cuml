
# Copyright (c) 2020, NVIDIA CORPORATION.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

import pytest
from cuml.test.utils import unit_param, \
                            quality_param, \
                            stress_param

from cuml.neighbors import KNeighborsClassifier as lKNNClf
from cuml.dask.neighbors import KNeighborsClassifier as dKNNClf

from sklearn.datasets import make_multilabel_classification
from sklearn.model_selection import train_test_split

import dask.array as da
from cuml.dask.common.dask_arr_utils import to_dask_cudf
from cudf.core.dataframe import DataFrame
import numpy as np


def generate_dask_array(np_array, n_parts):
    n_samples = np_array.shape[0]
    n_samples_per_part = int(n_samples / n_parts)
    chunks = [n_samples_per_part] * n_parts
    chunks[-1] += n_samples % n_samples_per_part
    chunks = tuple(chunks)
    return da.from_array(np_array, chunks=(chunks, -1))


@pytest.fixture(
    scope="module",
    params=[
        unit_param({'n_samples': 3000, 'n_features': 30,
                    'n_classes': 5, 'n_targets': 2}),
        quality_param({'n_samples': 8000, 'n_features': 35,
                       'n_classes': 12, 'n_targets': 3}),
        stress_param({'n_samples': 20000, 'n_features': 40,
                      'n_classes': 12, 'n_targets': 4})
    ])
def dataset(request):
    X, y = make_multilabel_classification(
        n_samples=int(request.param['n_samples'] * 1.2),
        n_features=request.param['n_features'],
        n_classes=request.param['n_classes'],
        n_labels=request.param['n_classes'],
        length=request.param['n_targets'])
    new_x = []
    new_y = []
    for i in range(y.shape[0]):
        a = np.argwhere(y[i] == 1)[:, 0]
        if len(a) >= request.param['n_targets']:
            new_x.append(i)
            np.random.shuffle(a)
            a = a[:request.param['n_targets']]
            new_y.append(a)
        if len(new_x) >= request.param['n_samples']:
            break
    X = X[new_x]
    noise = np.random.normal(0, 1.2, X.shape)
    X += noise
    y = np.array(new_y)

    return train_test_split(X, y, test_size=0.1)


def exact_match(output1, output2):
    l1, i1, d1 = output1
    l2, i2, d2 = output2
    l2 = l2.squeeze()

    # Check shapes
    assert l1.shape == l2.shape
    assert i1.shape == i2.shape
    assert d1.shape == d2.shape

    # Distances should match
    d1 = np.round(d1, 4)
    d2 = np.round(d2, 4)
    assert np.mean(d1 == d2) > 0.98

    # Indices should match
    correct_queries = (i1 == i2).all(axis=1)
    assert np.mean(correct_queries) > 0.95

    # Labels should match
    correct_queries = (l1 == l2).all(axis=1)
    assert np.mean(correct_queries) > 0.95


def check_probabilities(l_probas, d_probas):
    assert len(l_probas) == len(d_probas)
    for i in range(len(l_probas)):
        assert l_probas[i].shape == d_probas[i].shape
        assert np.array_equal(l_probas[i], d_probas[i])


@pytest.mark.parametrize("datatype", ['dask_array', 'dask_cudf'])
@pytest.mark.parametrize("n_neighbors", [1, 3, 8])
@pytest.mark.parametrize("n_parts", [2, 4, 12])
@pytest.mark.parametrize("batch_size", [128, 1024])
def test_predict_and_score(dataset, datatype, n_neighbors,
                           n_parts, batch_size, client):
    X_train, X_test, y_train, y_test = dataset
    np_y_test = y_test

    l_model = lKNNClf(n_neighbors=n_neighbors)
    l_model.fit(X_train, y_train)
    l_distances, l_indices = l_model.kneighbors(X_test)
    l_labels = l_model.predict(X_test)
    local_out = (l_labels, l_indices, l_distances)
    handmade_local_score = np.mean(y_test == l_labels)
    handmade_local_score = round(handmade_local_score, 3)

    X_train = generate_dask_array(X_train, n_parts)
    X_test = generate_dask_array(X_test, n_parts)
    y_train = generate_dask_array(y_train, n_parts)
    y_test = generate_dask_array(y_test, n_parts)

    if datatype == 'dask_cudf':
        X_train = to_dask_cudf(X_train, client)
        X_test = to_dask_cudf(X_test, client)
        y_train = to_dask_cudf(y_train, client)
        y_test = to_dask_cudf(y_test, client)

    d_model = dKNNClf(client=client, n_neighbors=n_neighbors,
                      batch_size=batch_size)
    d_model.fit(X_train, y_train)
    d_labels, d_indices, d_distances = \
        d_model.predict(X_test, convert_dtype=True)
    distributed_out = da.compute(d_labels, d_indices, d_distances)
    if datatype == 'dask_array':
        distributed_score = d_model.score(X_test, y_test)
        distributed_score = round(distributed_score, 3)

    if datatype == 'dask_cudf':
        distributed_out = list(map(lambda o: o.as_matrix()
                                   if isinstance(o, DataFrame)
                                   else o.to_array()[..., np.newaxis],
                                   distributed_out))

    exact_match(local_out, distributed_out)

    if datatype == 'dask_array':
        assert distributed_score == handmade_local_score
    else:
        y_pred = distributed_out[0]
        handmade_distributed_score = np.mean(np_y_test == y_pred)
        handmade_distributed_score = round(handmade_distributed_score, 3)
        assert handmade_distributed_score == handmade_local_score


@pytest.mark.parametrize("datatype", ['dask_array', 'dask_cudf'])
@pytest.mark.parametrize("n_neighbors", [1, 3, 8])
@pytest.mark.parametrize("n_parts", [2, 4, 12])
@pytest.mark.parametrize("batch_size", [128, 1024])
def test_predict_proba(dataset, datatype, n_neighbors,
                       n_parts, batch_size, client):
    X_train, X_test, y_train, y_test = dataset

    l_model = lKNNClf(n_neighbors=n_neighbors)
    l_model.fit(X_train, y_train)
    l_probas = l_model.predict_proba(X_test)

    X_train = generate_dask_array(X_train, n_parts)
    X_test = generate_dask_array(X_test, n_parts)
    y_train = generate_dask_array(y_train, n_parts)

    if datatype == 'dask_cudf':
        X_train = to_dask_cudf(X_train, client)
        X_test = to_dask_cudf(X_test, client)
        y_train = to_dask_cudf(y_train, client)

    d_model = dKNNClf(client=client, n_neighbors=n_neighbors)
    d_model.fit(X_train, y_train)
    d_probas = d_model.predict_proba(X_test, convert_dtype=True)
    d_probas = da.compute(d_probas)[0]

    if datatype == 'dask_cudf':
        d_probas = list(map(lambda o: o.as_matrix()
                            if isinstance(o, DataFrame)
                            else o.to_array()[..., np.newaxis],
                            d_probas))

    check_probabilities(l_probas, d_probas)
