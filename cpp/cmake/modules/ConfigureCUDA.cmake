#=============================================================================
# Copyright (c) 2018-2021, NVIDIA CORPORATION.
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
#=============================================================================

# todo (DD): Change cuda flags environment variables to use generators to enable using
# clang as per suggestion from mdemoret:
# target_compile_options(CUML
#     PUBLIC
#       $<$<AND:$<CUDA_COMPILER_ID:NVIDIA>,$<COMPILE_LANGUAGE:CUDA>>:
#         --expt-extended-lambda
#         --expt-relaxed-constexpr
#         -Xcudafe
#         --diag_suppress=unrecognized_gcc_pragma
#         -ccbin ${CMAKE_CXX_COMPILER}>
#     PRIVATE
#       $<$<AND:$<BOOL:${LINE_INFO}>,$<COMPILE_LANGUAGE:CUDA>>:-lineinfo>
#       $<$<AND:$<BOOL:${KERNEL_INFO}>,$<COMPILE_LANGUAGE:CUDA>>:-Xptxas=-v>
#       $<$<CUDA_COMPILER_ID:Clang>:-Wno-everything>
#   )

if(CMAKE_COMPILER_IS_GNUCXX)
    list(APPEND CUML_CXX_FLAGS -Wall -Werror -Wno-unknown-pragmas -Wno-error=deprecated-declarations)
    if(CUML_BUILD_TESTS OR CUML_BUILD_BENCHMARKS)
        # Suppress parentheses warning which causes gmock to fail
        list(APPEND CUML_CUDA_FLAGS -Xcompiler=-Wno-parentheses)
    endif()
endif()

list(APPEND CUML_CUDA_FLAGS --expt-extended-lambda --expt-relaxed-constexpr)

# set warnings as errors
# list(APPEND CUML_CUDA_FLAGS -Werror=cross-execution-space-call)
# list(APPEND CUML_CUDA_FLAGS -Xcompiler=-Wall,-Werror,-Wno-error=deprecated-declarations)

if(DISABLE_DEPRECATION_WARNING)
    list(APPEND CUML_CXX_FLAGS -Wno-deprecated-declarations)
    list(APPEND CUML_CUDA_FLAGS -Xcompiler=-Wno-deprecated-declarations)
endif()

# Option to enable line info in CUDA device compilation to allow introspection when profiling / memchecking
if(CUDA_ENABLE_LINEINFO)
    list(APPEND CUML_CUDA_FLAGS -lineinfo)
endif()

# Debug options
if(CMAKE_BUILD_TYPE MATCHES Debug)
    message(VERBOSE "CUML: Building with debugging flags")
    list(APPEND CUML_CUDA_FLAGS -G -Xcompiler=-rdynamic)
endif()
