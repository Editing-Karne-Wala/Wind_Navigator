#include <iostream>
#include <fstream>
#include <vector>
#include <string>

using namespace std;

// The Embedded C++ Engine designed to be called instantly by the FastAPI layer
int WIDTH = 0;
int HEIGHT = 0; // Represents Y-axis on map (Latitude map depth)
const int DEPTH = 30; // Z-axis altitude limit (Voxels, mapping approx up to 150m)

const int cx[19] = {0,  1, -1,  0,  0,  0,  0,   1, -1,  1, -1,   1, -1,  1, -1,   0,  0,  0,  0};
const int cy[19] = {0,  0,  0,  1, -1,  0,  0,   1, -1, -1,  1,   0,  0,  0,  0,   1, -1,  1, -1};
const int cz[19] = {0,  0,  0,  0,  0,  1, -1,   0,  0,  0,  0,   1, -1, -1,  1,   1, -1, -1,  1};
const int w[19]  = {12, 2,  2,  2,  2,  2,  2,   1,  1,  1,  1,   1,  1,  1,  1,   1,  1,  1,  1};
const int reverse_dir[19] = {0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15, 18, 17};

struct Voxel { int64_t f[19]; bool is_wall; };
Voxel*** grid1;
Voxel*** grid2;
Voxel*** current_g;
Voxel*** next_g;

bool load_terrain(const string& filename) {
    ifstream file(filename);
    if (!file.is_open()) return false;
    file >> WIDTH >> HEIGHT;
    
    grid1 = new Voxel**[DEPTH];
    grid2 = new Voxel**[DEPTH];
    for (int z = 0; z < DEPTH; z++) {
        grid1[z] = new Voxel*[HEIGHT];
        grid2[z] = new Voxel*[HEIGHT];
        for (int y = 0; y < HEIGHT; y++) {
            grid1[z][y] = new Voxel[WIDTH];
            grid2[z][y] = new Voxel[WIDTH];
            for(int x=0; x<WIDTH;x++) {
                for(int i=0; i<19; i++) {
                    grid1[z][y][x].f[i] = 0;
                    grid2[z][y][x].f[i] = 0;
                }
                // Box exterior boundary check
                bool wall = (x == 0 || x == WIDTH - 1 || y == 0 || y == HEIGHT - 1 || z == 0 || z == DEPTH - 1);
                grid1[z][y][x].is_wall = wall;
                grid2[z][y][x].is_wall = wall;
            }
        }
    }
    
    // Parse the 2D OpenStreetMap terrain into accurate 3D Voxel Pillars
    for(int y=0; y<HEIGHT; y++) {
        for(int x=0; x<WIDTH; x++) {
            int height_m;
            file >> height_m;
            int z_voxels = height_m / 5; // 1 Z-voxel = 5 meters of vertical true height
            if (z_voxels >= DEPTH) z_voxels = DEPTH - 1;
            
            for(int z=0; z<=z_voxels; z++) {
                grid1[z][y][x].is_wall = true;
                grid2[z][y][x].is_wall = true;
            }
        }
    }
    current_g = grid1;
    next_g = grid2;
    return true;
}

void lbm_step() {
    for (int z = 1; z < DEPTH - 1; z++)
        for (int y = 1; y < HEIGHT - 1; y++)
            for (int x = 1; x < WIDTH - 1; x++)
                for(int i=0; i<19; i++) next_g[z][y][x].f[i] = 0;

    for (int z = 1; z < DEPTH - 1; z++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                if (current_g[z][y][x].is_wall) continue;
                for (int i = 0; i < 19; i++) {
                    int64_t mass = current_g[z][y][x].f[i];
                    if (mass == 0) continue;
                    int nz = z + cz[i], ny = y + cy[i], nx = x + cx[i];
                    if (current_g[nz][ny][nx].is_wall) next_g[z][y][x].f[reverse_dir[i]] += mass;
                    else next_g[nz][ny][nx].f[i] += mass;
                }
            }
        }
    }

    for (int z = 1; z < DEPTH - 1; z++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                if (next_g[z][y][x].is_wall) continue;
                int64_t total_mass = 0;
                for (int i = 0; i < 19; i++) total_mass += next_g[z][y][x].f[i];
                if (total_mass > 0) {
                    int64_t distributed_mass = 0;
                    for (int i = 0; i < 19; i++) {
                        int64_t eq = (total_mass * w[i]) / 36; 
                        next_g[z][y][x].f[i] = eq; 
                        distributed_mass += eq;
                    }
                    next_g[z][y][x].f[0] += (total_mass - distributed_mass);
                }
            }
        }
    }

    Voxel*** temp = current_g; current_g = next_g; next_g = temp;
}

int main(int argc, char* argv[]) {
    if (argc < 4) { cout << "ERROR: Coordinate Params missing (X, Y, Z)\n"; return 1; }
    
    // GPS request converted to discrete Voxel Array Indices
    int target_x = stoi(argv[1]);
    int target_y = stoi(argv[2]);
    int target_z = stoi(argv[3]);

    if (!load_terrain("urban_terrain.txt")) { cout << "ERROR: Terrain load failed\n"; return 1; }

    // Inject heavy Easterly wind to simulate a storm front pushing through Manhattan
    for(int z=1; z<DEPTH-1; z++)
        for(int y=1; y<HEIGHT-1; y++)
            if(!current_g[z][y][2].is_wall) current_g[z][y][2].f[1] = 50000;

    // Run engine at incredible speed to simulate reality before the drone arrives
    for (int step = 0; step < 200; step++) lbm_step();

    // Structural failure checks for bad Drone API routing requests
    if(target_x <= 0 || target_x >= WIDTH || target_y <= 0 || target_y >= HEIGHT || target_z <= 0 || target_z >= DEPTH) {
        cout << "VECTOR_RESULT: 0,0,0 (OUT OF BOUNDS)\n";
        return 0;
    }
    
    if(current_g[target_z][target_y][target_x].is_wall) {
        cout << "VECTOR_RESULT: 0,0,0 (DRONE COLLISION IMMINENT - RE-ROUTE REQUIRED)\n";
        return 0;
    }

    // Mathematical Macroscopic Velocity Extraction (Converting 19 Lattice vectors back to X,Y,Z reality)
    int64_t vx = 0, vy = 0, vz = 0;
    int64_t m = 0;
    for(int i=0; i<19; i++) {
        int64_t fi = current_g[target_z][target_y][target_x].f[i];
        m += fi;
        vx += fi * cx[i];
        vy += fi * cy[i];
        vz += fi * cz[i];
    }
    
    // The True Drone Wind Drag Vector
    if (m > 0) {
        vx /= m; vy /= m; vz /= m;
    }

    cout << "VECTOR_RESULT: " << vx << "," << vy << "," << vz << "\n";
    return 0;
}
