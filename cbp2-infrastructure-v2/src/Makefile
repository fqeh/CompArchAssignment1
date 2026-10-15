CXX		=	g++
CXXFLAGS	=	-g -O3 -Wall

.PHONY: all test sanitize clean

all:		predict predict_extra_credit

predict:	predict.cc trace.cc predictor.h branch.h trace.h my_predictor.h
		$(CXX) $(CXXFLAGS) -o predict predict.cc trace.cc

predict_extra_credit:        predict_extra_credit.cc trace.cc predictor.h branch.h trace.h my_predictor.h
		$(CXX) $(CXXFLAGS) -o predict_extra_credit predict_extra_credit.cc trace.cc

predictor_test: ../tests/predictor_test.cc predictor.h branch.h my_predictor.h
		$(CXX) $(CXXFLAGS) -I. -o $@ ../tests/predictor_test.cc

evaluate: ../tests/evaluate.cc trace.cc predictor.h branch.h trace.h my_predictor.h
		$(CXX) $(CXXFLAGS) -I. -o $@ ../tests/evaluate.cc trace.cc

test: predictor_test
		./predictor_test

sanitize:
		$(CXX) -g -O1 -Wall -fsanitize=address,undefined -fno-omit-frame-pointer -I. -o predictor_test_sanitize ../tests/predictor_test.cc
		./predictor_test_sanitize

clean:
		rm -f predict predict_extra_credit predictor_test predictor_test_sanitize evaluate
