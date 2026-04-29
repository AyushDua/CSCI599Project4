cmake_minimum_required(VERSION 3.20)
project(wasm_topic4_mvp C CXX)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# ── Module libraries (clean/no-bug builds) ──────────────────────────────────
add_library(codec STATIC src/codec.c)
target_include_directories(codec PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

add_library(parser STATIC src/parser.c)
target_include_directories(parser PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

add_library(stats STATIC src/stats.c)
target_include_directories(stats PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/src)

# ── Google Test ──────────────────────────────────────────────────────────────
include(FetchContent)
FetchContent_Declare(
  googletest
  URL https://github.com/google/googletest/archive/refs/tags/v1.14.0.zip
)
set(gtest_force_shared_crt ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(googletest)

include(GoogleTest)
enable_testing()

# ── Clean test binaries ──────────────────────────────────────────────────────
add_executable(test_codec tests/source/test_codec.cpp)
target_link_libraries(test_codec PRIVATE codec GTest::gtest_main)
gtest_discover_tests(test_codec)

add_executable(test_parser tests/source/test_parser.cpp)
target_link_libraries(test_parser PRIVATE parser GTest::gtest_main)
gtest_discover_tests(test_parser)

add_executable(test_stats tests/source/test_stats.cpp)
target_link_libraries(test_stats PRIVATE stats GTest::gtest_main)
gtest_discover_tests(test_stats)

# ── Bug-variant codec binaries (codec.c compiled directly with bug flag) ─────
foreach(BUG_FLAG B001 B003 B004 B005 B006 B007 B008)
  add_executable(test_codec_${BUG_FLAG}
    tests/source/test_codec.cpp
    src/codec.c)
  target_include_directories(test_codec_${BUG_FLAG} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_libraries(test_codec_${BUG_FLAG} PRIVATE GTest::gtest_main)
  target_compile_definitions(test_codec_${BUG_FLAG} PRIVATE
    CODEC_BUG_${BUG_FLAG}=1)
endforeach()

# ── Bug-variant parser binaries ───────────────────────────────────────────────
foreach(BUG_FLAG Q001 Q002 Q003 Q004)
  add_executable(test_parser_${BUG_FLAG}
    tests/source/test_parser.cpp
    src/parser.c)
  target_include_directories(test_parser_${BUG_FLAG} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_libraries(test_parser_${BUG_FLAG} PRIVATE GTest::gtest_main)
  target_compile_definitions(test_parser_${BUG_FLAG} PRIVATE
    PARSER_BUG_${BUG_FLAG}=1)
endforeach()

# ── Bug-variant stats binaries ────────────────────────────────────────────────
foreach(BUG_FLAG S001 S002 S003 S004)
  add_executable(test_stats_${BUG_FLAG}
    tests/source/test_stats.cpp
    src/stats.c)
  target_include_directories(test_stats_${BUG_FLAG} PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src)
  target_link_libraries(test_stats_${BUG_FLAG} PRIVATE GTest::gtest_main)
  target_compile_definitions(test_stats_${BUG_FLAG} PRIVATE
    STATS_BUG_${BUG_FLAG}=1)
endforeach()
