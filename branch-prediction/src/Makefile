# Assignment build and verification targets. Author: Ali Alfageeh.
CXX ?= g++
CXXFLAGS ?= -std=c++17 -O3 -Wall -Wextra -pedantic
HEADERS = predictor.h branch.h trace.h my_predictor.h comparison_predictors.h

.PHONY: all test sanitize clean extra
all: predict

predict: predict.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ predict.cc trace.cc

test_predictor: ../tests/test_predictor.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -I. -o $@ ../tests/test_predictor.cc

test: predict test_predictor
	./test_predictor
	python3 ../tests/test_cli.py

sanitize:
	$(CXX) -std=c++17 -g -O1 -Wall -Wextra -pedantic \
	    -fsanitize=address,undefined -fno-omit-frame-pointer -I. \
	    -o test_predictor_san ../tests/test_predictor.cc
	./test_predictor_san

# Supplied extra-credit skeleton only; NOT part of the completed assignment.
extra: predict_extra_credit
predict_extra_credit: predict_extra_credit.cc trace.cc $(HEADERS)
	$(CXX) $(CXXFLAGS) -o $@ predict_extra_credit.cc trace.cc

clean:
	rm -f predict predict_extra_credit test_predictor test_predictor_san
