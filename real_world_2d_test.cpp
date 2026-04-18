#include <iostream>
#include <fstream>
#include <vector>
#include <string>

using namespace std;

// D2Q9 Base Math
const int cx[9] = {0, 1, 0, -1, 0,  1, -1, -1,  1};
const int cy[9] = {0, 0, 1,  0, -1,  1,  1, -1, -1};
const int w[9] = {16, 4, 4, 4, 4, 1, 1, 1, 1};
const int reverse_dir[9] = {0, 3, 4, 1, 2, 7, 8, 5, 6};

struct Voxel { int64_t f[9]; bool is_wall; };

int GRID_WIDTH = 0;
int GRID_HEIGHT = 0;

Voxel** current_g;
Voxel** next_g;

// --- LOAD TERRAIN MASK ---
bool load_terrain(const string& filename) {
    ifstream file(filename);
    if (!file.is_open()) {
        cout << "ERROR: Cannot open " << filename << "\n";
        return false;
    }
    
    file >> GRID_WIDTH >> GRID_HEIGHT;
    cout << "[*] Map detected: " << GRID_WIDTH << "x" << GRID_HEIGHT << "\n";
    
    // Allocate memory dynamically
    current_g = new Voxel*[GRID_HEIGHT];
    next_g = new Voxel*[GRID_HEIGHT];
    for(int y=0; y<GRID_HEIGHT; y++) {
        current_g[y] = new Voxel[GRID_WIDTH];
        next_g[y] = new Voxel[GRID_WIDTH];
        for(int x=0; x<GRID_WIDTH; x++) {
            for(int i=0; i<9; i++) {
                current_g[y][x].f[i] = 0;
                next_g[y][x].f[i] = 0;
            }
            int height;
            file >> height;
            
            // If the building height > 0, it acts as an absolute wall in our 2D cross-section
            bool wall = (height > 0) || (x == 0 || x == GRID_WIDTH - 1 || y == 0 || y == GRID_HEIGHT - 1);
            current_g[y][x].is_wall = wall;
            next_g[y][x].is_wall = wall;
        }
    }
    return true;
}

// --- INTEGER RELAXATION CORE ---
void lbm_step() {
    for (int y = 1; y < GRID_HEIGHT - 1; y++)
        for (int x = 1; x < GRID_WIDTH - 1; x++)
            if (!current_g[y][x].is_wall)
                for(int i=0; i<9; i++) next_g[y][x].f[i] = 0; 
                
    // 1. Streaming
    for (int y = 1; y < GRID_HEIGHT - 1; y++) {
        for (int x = 1; x < GRID_WIDTH - 1; x++) {
            if (current_g[y][x].is_wall) continue;

            for (int i = 0; i < 9; i++) {
                int64_t mass = current_g[y][x].f[i];
                if (mass == 0) continue;

                int nx = x + cx[i];
                int ny = y + cy[i];

                if (current_g[ny][nx].is_wall) {
                    next_g[y][x].f[reverse_dir[i]] += mass; // Perfectly reversed bounce
                } else {
                    next_g[ny][nx].f[i] += mass;
                }
            }
        }
    }

    // 2. Remainder Vault Collision
    for (int y = 1; y < GRID_HEIGHT - 1; y++) {
        for (int x = 1; x < GRID_WIDTH - 1; x++) {
            if (next_g[y][x].is_wall) continue;

            int64_t total_mass = 0;
            for (int i=0; i<9; i++) total_mass += next_g[y][x].f[i];

            if (total_mass > 0) {
                int64_t distributed_mass = 0;
                for (int i = 0; i < 9; i++) {
                    int64_t eq = (total_mass * w[i]) / 36; 
                    next_g[y][x].f[i] = eq; 
                    distributed_mass += eq;
                }
                next_g[y][x].f[0] += (total_mass - distributed_mass);
            }
        }
    }

    Voxel** temp = current_g;
    current_g = next_g;
    next_g = temp;
}

int64_t get_total_mass() {
    int64_t m = 0;
    for (int y = 0; y < GRID_HEIGHT; y++)
        for (int x = 0; x < GRID_WIDTH; x++)
            if (!current_g[y][x].is_wall)
                for (int i = 0; i < 9; i++) m += current_g[y][x].f[i];
    return m;
}

int main() {
    cout << "===== URBAN 2D METEOROLOGICAL STRESS TEST =====\n\n";
    if (!load_terrain("urban_terrain.txt")) return 1;

    // Inject massive ambient air mass into the streets
    for (int y = 1; y < GRID_HEIGHT - 1; y++) {
        for (int x = 1; x < GRID_WIDTH - 1; x++) {
            if (!current_g[y][x].is_wall) {
                current_g[y][x].f[0] = 50000;
            }
        }
    }
    
    // Inject a violent continuous cross-wind from the West
    for(int y=1; y<GRID_HEIGHT-1; y++) {
         if (!current_g[y][2].is_wall) {
             current_g[y][2].f[1] = 900000; // Strong Eastward flow Vector
         }
    }

    int64_t start_mass = get_total_mass();
    cout << "Absolute Street Mass Pre-Windstorm: " << start_mass << "\n";
    cout << "Executing 5,000 frames of turbulent urban flow...\n";

    for (int step = 1; step <= 5000; step++) {
        lbm_step();
        
        if (step % 1000 == 0) {
            int64_t current = get_total_mass();
            cout << "  Frame " << step << " | Mass: " << current;
            if (current != start_mass) {
                cout << " [CRITICAL LEAK]\n";
                return 1;
            } else {
                cout << " [STABLE]\n";
            }
        }
    }

    cout << "\n[+] URBAN 2D TEST COMPLETED.\n";
    cout << "[+] Despite chaotic city architecture causing massive integer sheer, Math remains strictly indestructible.\n";
    
    return 0;
}
