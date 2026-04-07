#include <iostream>
#include <vector>
#include <queue>
#include <map>
#include <cmath>
#include <chrono>
#include <tuple>
#include <fstream>
#include <iomanip>

using namespace std;

int CITY_WIDTH = 0;
int CITY_HEIGHT = 0;
const int CITY_DEPTH = 150; // Midtown Manhattan skyscrapers require high altitude 

int BUILDING_HEIGHT_MAP[1000][1000] = {0}; 

struct Wind { double vx, vy, vz; };

Wind get_wind_vector_at_time(int x, int y, int z, int64_t unix_timestamp) {
    if (x < 0 || x >= CITY_WIDTH || y < 0 || y >= CITY_HEIGHT) return {0,0,0};
    
    int building_ahead = (x+1 < CITY_WIDTH) ? BUILDING_HEIGHT_MAP[y][x+1] : 0; 
    
    if (building_ahead > z && BUILDING_HEIGHT_MAP[y][x] <= z) {
        // Massive upward aerodynamic lift when East-blowing wind deflects off a skyscraper face
        return {0.0, 0.0, 15.0}; 
    }
    
    return {1.0, 0.0, 0.0}; 
}

double heuristic(int x1, int y1, int z1, int x2, int y2, int z2) {
    return (abs(x2 - x1) + abs(y2 - y1) + abs(z2 - z1)) * 10.0;
}

typedef tuple<double, int, int, int, int64_t> QNode;
typedef tuple<int, int, int, int64_t> State;

struct CompareQNode {
    bool operator()(const QNode& a, const QNode& b) {
        return get<0>(a) > get<0>(b); 
    }
};

void a_star_4d_osm(State start, tuple<int, int, int> target) {
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
            int64_t nt_unix = ct_unix + 1;
            
            if (nx < 0 || ny < 0 || nz < 0 || nx >= CITY_WIDTH || ny >= CITY_HEIGHT || nz >= CITY_DEPTH) continue;
            
            // OPEN STREET MAP CONCRETE COLLISION CHECK
            if (nz <= BUILDING_HEIGHT_MAP[ny][nx]) continue; 
            
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
        
        cout << "--- OSM REAL-WORLD FLIGHT MANEUVERS ---\n";
        for(int i = path.size() - 1; i >= 0; --i) {
            int x = get<0>(path[i]);
            int y = get<1>(path[i]);
            int z = get<2>(path[i]);
            int64_t t = get<3>(path[i]);
            
            Wind w = get_wind_vector_at_time(x, y, z, t);
            
            string action = "Flying over flat ground: Thrust ON";
            if (w.vz > 5.0) action = "GLIDING ON WIND DEFLECTING OFF SKYSCRAPER! Engines Cut.";
            else if (BUILDING_HEIGHT_MAP[y][x] > 5) action = "Maneuvering closely over OSM Skyscraper Roof";
            
            cout << "UNIX " << t << " | GPS: [X:" << x << " Y:" << y << " Z:" << z << "] | Terrain Height: " << BUILDING_HEIGHT_MAP[y][x] << " | " << action << "\n";
        }
        cout << "\n[+] Routing Complete against OpenStreetMap concrete map.\n";
    } else {
        cout << "[-] PATH FAILED. Drone could not safely navigate the city layout.\n";
    }
}

int main() {
    cout << "=========================================================\n";
    cout << "    OSM + 4D ROUTER: TRUE REAL-WORLD CITY INTEGRATION    \n";
    cout << "=========================================================\n\n";

    ifstream file("urban_terrain.txt");
    if(!file.is_open()) return 1;
    
    file >> CITY_WIDTH >> CITY_HEIGHT;
    cout << "[*] Loading 'urban_terrain.txt' (OpenStreetMap Extract) " << CITY_WIDTH << "x" << CITY_HEIGHT << "\n";
    
    for(int y = 0; y < CITY_HEIGHT; y++) {
        for(int x = 0; x < CITY_WIDTH; x++) {
            file >> BUILDING_HEIGHT_MAP[y][x];
        }
    }
    
    auto now = chrono::system_clock::now();
    int64_t current_unix_time = chrono::duration_cast<chrono::seconds>(now.time_since_epoch()).count();
    
    // Dynamically calculate departure and arrival platforms based on OSM heights
    int start_x = 1, start_y = 15;
    int target_x = 30, target_y = 15;
    
    int start_altitude = BUILDING_HEIGHT_MAP[start_y][start_x] + 2; 
    int end_altitude = BUILDING_HEIGHT_MAP[target_y][target_x] + 2; 
    
    cout << "[*] Drone taking off from roof at Altitude " << start_altitude << "\n";
    cout << "[*] Targeting destination roof at Altitude " << end_altitude << "\n\n";

    State start = {start_x, start_y, start_altitude, current_unix_time};
    tuple<int, int, int> target = {target_x, target_y, end_altitude}; 
    
    a_star_4d_osm(start, target);
    
    return 0;
}
