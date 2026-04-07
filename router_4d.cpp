#include <iostream>
#include <vector>
#include <queue>
#include <map>
#include <cmath>
#include <chrono>
#include <tuple>
#include <iomanip>

using namespace std;

// Physical Grid Constraints
const int WIDTH = 50;
const int HEIGHT = 50;
const int DEPTH = 20;

struct Wind { double vx, vy, vz; };

Wind get_wind_vector_at_time(int x, int y, int z, int64_t unix_timestamp) {
    // We map the physical vortex to absolute Universal Time (UNIX Epoch).
    // Modulo 100 ensures the vortex cycles exactly predictably synced to atomic clocks.
    int cycle_time = unix_timestamp % 100;
    int vortex_center_x = 15 + (cycle_time / 2);
    int vortex_center_y = 25;
    
    if (abs(x - vortex_center_x) <= 2 && abs(y - vortex_center_y) <= 2) {
        return {2.0, 0.0, 8.0}; // Updraft detected
    }
    return {-1.0, 0.0, 0.0}; // Default ambient wind
}

double heuristic(int x1, int y1, int z1, int x2, int y2, int z2) {
    return (abs(x2 - x1) + abs(y2 - y1) + abs(z2 - z1)) * 10.0;
}

// QNode: F_score, X, Y, Z, UNIX_T
typedef tuple<double, int, int, int, int64_t> QNode;

// State: X, Y, Z, UNIX_T
typedef tuple<int, int, int, int64_t> State;

struct CompareQNode {
    bool operator()(const QNode& a, const QNode& b) {
        return get<0>(a) > get<0>(b); 
    }
};

void a_star_4d(State start, tuple<int, int, int> target) {
    priority_queue<QNode, vector<QNode>, CompareQNode> open_set;
    map<State, State> came_from;
    map<State, double> g_score;
    
    g_score[start] = 0;
    open_set.push({0.0, get<0>(start), get<1>(start), get<2>(start), get<3>(start)});
    
    int tx = get<0>(target), ty = get<1>(target), tz = get<2>(target);
    int moves[6][3] = { {1,0,0}, {-1,0,0}, {0,1,0}, {0,-1,0}, {0,0,1}, {0,0,-1} };
    
    bool found = false;
    State final_state;

    while(!open_set.empty()) {
        QNode current = open_set.top();
        open_set.pop();
        
        int cx = get<1>(current);
        int cy = get<2>(current);
        int cz = get<3>(current);
        int64_t ct_unix = get<4>(current);
        State cur_state = {cx, cy, cz, ct_unix};
        
        if (cx == tx && cy == ty && cz == tz) {
            found = true;
            final_state = cur_state;
            break;
        }
        
        for(int i=0; i<6; ++i) {
            int nx = cx + moves[i][0];
            int ny = cy + moves[i][1];
            int nz = cz + moves[i][2];
            int64_t nt_unix = ct_unix + 1; // 1 second flight per Voxel translation
            
            if (nx < 0 || ny < 0 || nz < 0 || nx >= WIDTH || ny >= HEIGHT || nz >= DEPTH) continue;
            
            Wind w = get_wind_vector_at_time(nx, ny, nz, nt_unix);
            double wind_assist = (moves[i][0] * w.vx) + (moves[i][1] * w.vy) + (moves[i][2] * w.vz);
            double movement_cost = max(1.0, 10.0 - (wind_assist * 1.5));
            
            State neighbor = {nx, ny, nz, nt_unix};
            double tentative_g_score = g_score[cur_state] + movement_cost;
            
            if (g_score.find(neighbor) == g_score.end() || tentative_g_score < g_score[neighbor]) {
                came_from[neighbor] = cur_state;
                g_score[neighbor] = tentative_g_score;
                double f_score = tentative_g_score + heuristic(nx, ny, nz, tx, ty, tz);
                open_set.push({f_score, nx, ny, nz, nt_unix});
            }
        }
    }
    
    if (found) {
        vector<State> path;
        State curr = final_state;
        while(came_from.find(curr) != came_from.end()) {
            path.push_back(curr);
            curr = came_from[curr];
        }
        path.push_back(start);
        
        cout << "--- GENERATED ABSOLUTE FLIGHT PLAN (C++ IOT CORE) ---\n";
        for(int i = path.size() - 1; i >= 0; --i) {
            int x = get<0>(path[i]);
            int y = get<1>(path[i]);
            int z = get<2>(path[i]);
            int64_t t = get<3>(path[i]);
            
            Wind w = get_wind_vector_at_time(x, y, z, t);
            
            string action = "PROP: Normal Thrust";
            if (w.vz >= 8.0) action = "GLIDE: Motors Cut (Surfing Thermal)";
            else if (w.vx < -0.5) action = "PROP: High Thrust (Fighting Headwind)";
            
            cout << "UNIX Time: " << t << " | Voxel: [" << (x < 10 ? "0" : "") << x << ", " 
                                                        << (y < 10 ? "0" : "") << y << ", " 
                                                        << (z < 10 ? "0" : "") << z << "] "
                 << "| Wind Vz: " << w.vz << " | Action: " << action << "\n";
        }
        cout << "\n[+] Routing Complete on Embedded C++ IOT Chip.\n";
    } else {
        cout << "[-] PATH FAILED.\n";
    }
}

int main() {
    // Automatically poll the OS/Satellite Clock
    auto now = chrono::system_clock::now();
    int64_t current_unix_time = chrono::duration_cast<chrono::seconds>(now.time_since_epoch()).count();
    
    cout << "=========================================================\n";
    cout << "   PHASE 8: AEROSPACE 4D PATHFINDING (Onboard C++ IOT)   \n";
    cout << "=========================================================\n\n";
    cout << "[*] Fetching absolute atomic GPS Time: UNIX " << current_unix_time << "\n";
    cout << "[*] Running 4D UNIX-Synchronized A* Search on Flight Controller Loop...\n\n";
    
    State start = {10, 25, 5, current_unix_time};
    tuple<int, int, int> target = {30, 25, 15};
    
    a_star_4d(start, target);
    
    return 0;
}
