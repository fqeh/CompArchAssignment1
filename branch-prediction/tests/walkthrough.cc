// Deterministic step-through evidence. Author: Ali Alfageeh.
#include <iostream>
#include "branch.h"
#include "predictor.h"
#include "my_predictor.h"
int main() {
    pm_predictor p;
    const unsigned hashes[] = {1,2,1,3,2,3,4,3};
    const bool outcomes[] = {true,true,false,false,false,true,false,true};
    std::cout << "step,pc,ghr_before,local_index,local_counter,hash,set,tag,hit_way,prediction,actual,ghr_after,way0_tag,way0_counter,way1_tag,way1_counter,lru_way\n";
    for (unsigned i=0;i<8;++i) {
        unsigned before=p.history(),pc=hashes[i]^before;
        branch_info b{pc,0,BR_CONDITIONAL};
        auto *u=static_cast<pm_update *>(p.predict(b));
        unsigned local=p.local_counter(u->index);
        bool predicted=u->direction_prediction();
        std::cout<<i+1<<','<<pc<<','<<before<<','<<u->index<<','<<local<<','
            <<hashes[i]<<','<<u->set<<','<<u->tag<<','<<u->hit_way<<','<<predicted<<','<<outcomes[i]<<',';
        p.update(u,outcomes[i],0);
        std::cout<<p.history();
        for(unsigned w=0;w<2;++w) {
            const auto &e=p.global_entry(0,w);
            std::cout<<','<<(e.valid ? static_cast<int>(e.tag) : -1)<<','<<static_cast<unsigned>(e.counter);
        }
        std::cout<<','<<p.next_victim(0)<<'\n';
    }
}
