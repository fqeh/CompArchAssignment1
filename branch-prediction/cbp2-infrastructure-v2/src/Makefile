CXX		=	g++
CXXFLAGS	=	-g -O3 -Wall -std=c++11

.PHONY: all clean extra_credit

all:		predict

extra_credit:	predict_extra_credit

predict:	predict.cc trace.cc predictor.h branch.h trace.h my_predictor.h
		$(CXX) $(CXXFLAGS) -o predict predict.cc trace.cc

predict_extra_credit:        predict_extra_credit.cc trace.cc predictor.h branch.h trace.h my_predictor.h
		$(CXX) $(CXXFLAGS) -o predict_extra_credit predict_extra_credit.cc trace.cc


clean:
		rm -f predict predict_extra_credit
