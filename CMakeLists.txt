cmake_minimum_required(VERSION 3.20)
project(wasm_topic4_mvp C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

add_library(codec STATIC src/codec.c)
target_include_directories(codec PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

enable_testing()
add_executable(test_codec tests/source/test_codec.cpp)
target_link_libraries(test_codec PRIVATE codec GTest::gtest_main)

include(GoogleTest)
gtest_discover_tests(test_codec)