#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {

std::string repeat_hex(const std::string& byte_hex, size_t count) {
  std::string out;
  out.reserve(byte_hex.size() * count);
  for (size_t i = 0; i < count; ++i) {
    out += byte_hex;
  }
  return out;
}

std::vector<std::pair<std::string, std::string>> fixed_cases(const std::string& mode) {
  std::vector<std::pair<std::string, std::string>> cases = {
      {"stdin_empty", ""},
      {"stdin_hi", "6869"},
      {"stdin_ABC", "414243"},
      {"stdin_utf8_e_acute", "c3a9"},
      {"stdin_utf8_nihao", "e4bda0e5a5bd"},
      {"stdin_utf8_euro", "e282ac"},
      {"stdin_bytes_000102", "000102"},
      {"single_00", "00"},
      {"single_ff", "ff"},
      {"mixed_0001027f80ff", "0001027f80ff"},
      {"ascii_sentence", "5761736d206c617965722032"},
      {"repeating_ab_16", repeat_hex("ab", 16)},
      {"boundary_len_1", repeat_hex("42", 1)},
      {"boundary_len_2", repeat_hex("42", 2)},
      {"boundary_len_3", repeat_hex("42", 3)},
      {"boundary_len_255", repeat_hex("42", 255)},
      {"boundary_len_256", repeat_hex("42", 256)},
      {"boundary_len_1023", repeat_hex("42", 1023)},
      {"boundary_len_4096", repeat_hex("42", 4096)},
  };

  if (mode == "full") {
    cases.push_back({"boundary_len_4095", repeat_hex("37", 4095)});
  }

  return cases;
}

std::string hex_for_random_bytes(std::mt19937& rng, int length) {
  static const char* HEX = "0123456789abcdef";
  std::uniform_int_distribution<int> byte_dist(0, 255);

  std::string out;
  out.reserve(static_cast<size_t>(length) * 2);
  for (int i = 0; i < length; ++i) {
    const unsigned value = static_cast<unsigned>(byte_dist(rng));
    out.push_back(HEX[(value >> 4) & 0xF]);
    out.push_back(HEX[value & 0xF]);
  }
  return out;
}

struct Options {
  std::string mode;
  int random_cases = 0;
  int max_random_len = 0;
  int seed = 0;
};

Options parse_args(int argc, char** argv) {
  Options options;
  for (int i = 1; i < argc; ++i) {
    const std::string arg = argv[i];
    auto require_value = [&](const char* flag) -> std::string {
      if (i + 1 >= argc) {
        throw std::runtime_error(std::string("Missing value for ") + flag);
      }
      return argv[++i];
    };

    if (arg == "--mode") {
      options.mode = require_value("--mode");
    } else if (arg == "--random-cases") {
      options.random_cases = std::stoi(require_value("--random-cases"));
    } else if (arg == "--max-random-len") {
      options.max_random_len = std::stoi(require_value("--max-random-len"));
    } else if (arg == "--seed") {
      options.seed = std::stoi(require_value("--seed"));
    } else {
      throw std::runtime_error("Unknown argument: " + arg);
    }
  }

  if (options.mode != "fast" && options.mode != "full") {
    throw std::runtime_error("--mode must be fast or full");
  }
  if (options.random_cases < 0) {
    throw std::runtime_error("--random-cases must be >= 0");
  }
  if (options.max_random_len < 0) {
    throw std::runtime_error("--max-random-len must be >= 0");
  }

  return options;
}

}  // namespace

int main(int argc, char** argv) {
  try {
    const Options options = parse_args(argc, argv);

    for (const auto& test_case : fixed_cases(options.mode)) {
      std::cout << test_case.first << '\t' << test_case.second << '\n';
    }

    std::mt19937 rng(static_cast<std::mt19937::result_type>(options.seed));
    std::uniform_int_distribution<int> len_dist(0, options.max_random_len);

    for (int index = 0; index < options.random_cases; ++index) {
      const int length = len_dist(rng);
      std::cout << "random_seed_" << options.seed << '_' << index << '\t'
                << hex_for_random_bytes(rng, length) << '\n';
    }

    return 0;
  } catch (const std::exception& ex) {
    std::cerr << ex.what() << '\n';
    return 2;
  }
}