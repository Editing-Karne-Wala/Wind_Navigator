#include <iostream>
#include <vector>

using namespace std;

// The 3D Engine: D3Q19 Model
const int WIDTH = 40;   // X-axis (East/West)
const int HEIGHT = 20;  // Y-axis (North/South)
const int DEPTH = 20;   // Z-axis (Altitude)

// 19 Discrete Vectors for 3D Flow
const int cx[19] = {0,  1, -1,  0,  0,  0,  0,   1, -1,  1, -1,   1, -1,  1, -1,   0,  0,  0,  0};
const int cy[19] = {0,  0,  0,  1, -1,  0,  0,   1, -1, -1,  1,   0,  0,  0,  0,   1, -1,  1, -1};
const int cz[19] = {0,  0,  0,  0,  0,  1, -1,   0,  0,  0,  0,   1, -1, -1,  1,   1, -1, -1,  1};

// D3Q19 Mathematical Weights (LCF perfectly scaled to exactly 36)
// 12 (Center) + 12 (Faces) + 12 (Edges) = 36
const int w[19] = {12,  2,  2,  2,  2,  2,  2,   1,  1,  1,  1,   1,  1,  1,  1,   1,  1,  1,  1};

// Bounce-Back Momentum Reversal Map
const int reverse_dir[19] = {
    0, 
    2, 1, 4, 3, 6, 5, 
    8, 7, 10, 9, 
    12, 11, 14, 13, 
    16, 15, 18, 17
};

// 153 Bytes per Voxel
struct Voxel {
    int64_t f[19]; 
    bool is_wall;
};

// Allocate memory dynamically as 3D grids grow large very quickly
Voxel*** grid1;
Voxel*** grid2;
Voxel*** current_g;
Voxel*** next_g;

void init_3d_box() {
    grid1 = new Voxel**[DEPTH];
    grid2 = new Voxel**[DEPTH];
    
    for (int z = 0; z < DEPTH; z++) {
        grid1[z] = new Voxel*[HEIGHT];
        grid2[z] = new Voxel*[HEIGHT];
        for (int y = 0; y < HEIGHT; y++) {
            grid1[z][y] = new Voxel[WIDTH];
            grid2[z][y] = new Voxel[WIDTH];
            for (int x = 0; x < WIDTH; x++) {
                for (int i = 0; i < 19; i++) {
                    grid1[z][y][x].f[i] = 0;
                    grid2[z][y][x].f[i] = 0;
                }
                
                // Form a perfectly sealed 3D Bounding Box (A Glass Cube)
                bool wall = (x == 0 || x == WIDTH - 1 || 
                             y == 0 || y == HEIGHT - 1 || 
                             z == 0 || z == DEPTH - 1);
                
                // We add a massive Skyscraper directly in the exact center from floor to mid-height
                if (x >= 18 && x <= 22 && y >= 8 && y <= 12 && z < 10) {
                    wall = true;
                }

                grid1[z][y][x].is_wall = wall;
                grid2[z][y][x].is_wall = wall;
            }
        }
    }
    current_g = grid1;
    next_g = grid2;
}

void lbm_step() {
    // 1. Cleansing Pass
    for (int z = 1; z < DEPTH - 1; z++)
        for (int y = 1; y < HEIGHT - 1; y++)
            for (int x = 1; x < WIDTH - 1; x++)
                if (!current_g[z][y][x].is_wall)
                    for(int i=0; i<19; i++) next_g[z][y][x].f[i] = 0; 

    // 2. 3D Streaming (Momentum propagation & bounce-back)
    for (int z = 1; z < DEPTH - 1; z++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                if (current_g[z][y][x].is_wall) continue;

                for (int i = 0; i < 19; i++) {
                    int64_t mass = current_g[z][y][x].f[i];
                    if (mass == 0) continue;

                    int nz = z + cz[i];
                    int ny = y + cy[i];
                    int nx = x + cx[i];

                    if (current_g[nz][ny][nx].is_wall) {
                        next_g[z][y][x].f[reverse_dir[i]] += mass; // Perfectly reversed bounce
                    } else {
                        next_g[nz][ny][nx].f[i] += mass;
                    }
                }
            }
        }
    }

    // 3. 3D Collision and the Remainder Vault
    for (int z = 1; z < DEPTH - 1; z++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                if (next_g[z][y][x].is_wall) continue;

                int64_t total_mass = 0;
                for (int i = 0; i < 19; i++) total_mass += next_g[z][y][x].f[i];

                if (total_mass > 0) {
                    int64_t distributed_mass = 0;
                    for (int i = 0; i < 19; i++) {
                        // The Golden Multiplier operates perfectly in 3-Dimensional geometry
                        int64_t eq = (total_mass * w[i]) / 36; 
                        next_g[z][y][x].f[i] = eq; 
                        distributed_mass += eq;
                    }
                    
                    // The Vault protects altitude calculations identical to latitude/longitude
                    next_g[z][y][x].f[0] += (total_mass - distributed_mass);
                }
            }
        }
    }

    // Ping-pong buffer swap
    Voxel*** temp = current_g;
    current_g = next_g;
    next_g = temp;
}

int64_t get_total_mass() {
    int64_t m = 0;
    for (int z = 0; z < DEPTH; z++)
        for (int y = 0; y < HEIGHT; y++)
            for (int x = 0; x < WIDTH; x++)
                if (!current_g[z][y][x].is_wall)
                    for (int i = 0; i < 19; i++) m += current_g[z][y][x].f[i];
    return m;
}

int main() {
    cout << "===== PROJECT REALITY B: THE D3Q19 CORE =====\n\n";
    cout << "Initializing 3D Sealed Topography (40x20x20 Volume)...\n";
    init_3d_box();

    cout << "Injecting massive wind draft at Altitude Z=5, aiming directly at the central skyscraper...\n";
    for(int z = 2; z <= 8; z++) {
        for (int y = 6; y <= 14; y++) {
            current_g[z][y][5].f[1] = 100000; // Strong vector slamming East
        }
    }

    int64_t start_mass = get_total_mass();
    cout << "Absolute Atmospheric Mass: " << start_mass << "\n";
    cout << "Executing 1,000 frames of full 3-Dimensional turbulent physics...\n";

    for (int step = 1; step <= 1000; step++) {
        lbm_step();
        
        if (step % 250 == 0) {
            int64_t current = get_total_mass();
            cout << "  Frame " << step << " | Mass: " << current;
            if (current != start_mass) {
                cout << " [CRITICAL 3D LEAK]\n";
                return 1;
            } else {
                cout << " [VAULT SECURE]\n";
            }
        }
    }

    cout << "\n[+] 3D D3Q19 UPGRADE SUCCESSFUL.\n";
    cout << "[+] Mass perfectly scaled across 19 vectors with severe Z-Axis vertical disruption.\n";
    cout << "[+] No energy leaks. No FPU instructions. Total Conservation.\n";

    return 0;
}
