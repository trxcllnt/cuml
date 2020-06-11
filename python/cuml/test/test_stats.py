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
import cupy as cp

from cuml.prims.stats import cov
from cuml.test.utils import array_equal


@pytest.mark.parametrize("nrows", [1000])
@pytest.mark.parametrize("ncols", [500, 1500])
@pytest.mark.parametrize("sparse", [True, False])
@pytest.mark.parametrize("dtype", [cp.float32, cp.float64])
@pytest.mark.parametrize("copy", [True, False])
def test_cov(nrows, ncols, sparse, dtype, copy):
    if sparse:
        x = cp.sparse.random(nrows, ncols, density=0.07)
    else:
        x = cp.random.random((nrows, ncols))

    cov_result = cov(x, x, copy=copy)

    assert cov_result.shape == (ncols, ncols)

    local_gram = x.T.dot(x) * (1 / x.shape[0])
    local_mean = x.sum(axis=0) * (1 / x.shape[0])

    if cp.sparse.issparse(local_gram):
        local_gram = local_gram.todense()

    local_cov = local_gram - cp.outer(local_mean, local_mean)

    assert array_equal(cov_result, local_cov, 1e-7, with_sign=True)
