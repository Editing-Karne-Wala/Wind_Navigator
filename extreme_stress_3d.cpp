#include <iostream>
#include <vector>

using namespace std;

// 3D Grid Parameters
const int WIDTH = 20;
const int HEIGHT = 20;
const int DEPTH = 20;

// D3Q19 Constants
const int cx[19] = {0,  1, -1,  0,  0,  0,  0,   1, -1,  1, -1,   1, -1,  1, -1,   0,  0,  0,  0};
const int cy[19] = {0,  0,  0,  1, -1,  0,  0,   1, -1, -1,  1,   0,  0,  0,  0,   1, -1,  1, -1};
const int cz[19] = {0,  0,  0,  0,  0,  1, -1,   0,  0,  0,  0,   1, -1, -1,  1,   1, -1, -1,  1};
const int w[19] = {12,  2,  2,  2,  2,  2,  2,   1,  1,  1,  1,   1,  1,  1,  1,   1,  1,  1,  1};
const int reverse_dir[19] = {0, 2, 1, 4, 3, 6, 5, 8, 7, 10, 9, 12, 11, 14, 13, 16, 15, 18, 17};

struct Voxel {
    int64_t f[19]; 
    bool is_wall;
};

Voxel*** grid1;
Voxel*** grid2;
Voxel*** current_g;
Voxel*** next_g;

void init_grid() {
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
                // Exterior walls
                bool wall = (x == 0 || x == WIDTH - 1 || y == 0 || y == HEIGHT - 1 || z == 0 || z == DEPTH - 1);
                grid1[z][y][x].is_wall = wall;
                grid2[z][y][x].is_wall = wall;
            }
        }
    }
    current_g = grid1;
    next_g = grid2;
}

void lbm_step() {
    // Clean
    for (int z = 1; z < DEPTH - 1; z++)
        for (int y = 1; y < HEIGHT - 1; y++)
            for (int x = 1; x < WIDTH - 1; x++)
                for(int i=0; i<19; i++) next_g[z][y][x].f[i] = 0;

    // Stream
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

                    if (current_g[nz][ny][nx].is_wall) next_g[z][y][x].f[reverse_dir[i]] += mass;
                    else next_g[nz][ny][nx].f[i] += mass;
                }
            }
        }
    }

    // Collide
    for (int z = 1; z < DEPTH - 1; z++) {
        for (int y = 1; y < HEIGHT - 1; y++) {
            for (int x = 1; x < WIDTH - 1; x++) {
                if (next_g[z][y][x].is_wall) continue;

                int64_t total_mass = 0;
                for (int i = 0; i < 19; i++) total_mass += next_g[z][y][x].f[i];

                if (total_mass != 0) { // Support negative tests
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

void reset() {
    for (int z = 1; z < DEPTH - 1; z++)
        for (int y = 1; y < HEIGHT - 1; y++)
            for (int x = 1; x < WIDTH - 1; x++) {
                current_g[z][y][x].is_wall = false;
                next_g[z][y][x].is_wall = false;
                for(int i=0; i<19; i++) {
                    current_g[z][y][x].f[i] = 0;
                    next_g[z][y][x].f[i] = 0;
                }
            }
}

int main() {
    init_grid();
    cout << "===== D3Q19 RUTHLESS PHYSICS STRESS TEST =====\n\n";

    // TEST 1: The Triple-Corner Shear Trap
    // In 3D, a single corner shares 3 walls (X, Y, Z). 
    // If we throw indivisible mass straight into it, the diagonal bounce-backs overlapping can delete mass if the integer truncation cascades.
    cout << "--- TEST 1: The Triple-Corner Shear Trap ---\n";
    reset();
    current_g[1][1][1].f[14] = 97; // Indivisible 97 mass moving into the bottom-south-west corner
    int64_t s1 = get_total_mass();
    cout << "Injecting 97 mass into absolute Z,Y,X corner.\n";
    for(int i=0; i<100; i++) lbm_step();
    int64_t e1 = get_total_mass();
    cout << "Mass Pre: " << s1 << " | Post: " << e1;
    if(s1 != e1) cout << " [CRITICAL FAILURE: DIAGONAL COLLAPSE]\n"; else cout << " [STABLE]\n";

    // TEST 2: The Vertical Micro-Tornado (Integer Torsion)
    // Create an intense rotating shear in a 2x2x2 block. Opposing vectors in immediate neighbors cause math oscillation.
    cout << "\n--- TEST 2: The 2x2x2 Z-Axis Micro-Tornado ---\n";
    reset();
    current_g[10][10][10].f[1] = 50000; // East
    current_g[10][11][10].f[3] = 50000; // North
    current_g[10][11][11].f[2] = 50000; // West
    current_g[10][10][11].f[4] = 50000; // South
    
    current_g[9][10][10].f[5]  = -25000; // Negative updraft
    current_g[11][11][11].f[6] = 25000;  // Positive downdraft
    
    int64_t s2 = get_total_mass();
    cout << "Injecting violent rotational shear with negative altitudes.\n";
    for(int i=0; i<250; i++) lbm_step();
    int64_t e2 = get_total_mass();
    cout << "Mass Pre: " << s2 << " | Post: " << e2;
    if(s2 != e2) cout << " [CRITICAL FAILURE: TORSION FRACTURE]\n"; else cout << " [STABLE]\n";

    // TEST 3: The Z-Axis Supersonic "Pancake" (Ceiling to Floor Slam)
    // 1 Quintillion mass thrown straight down from the ceiling to hit the floor.
    // Tests if the 6 downward vectors all perfectly reflect UP and distribute the remainder to the center.
    cout << "\n--- TEST 3: The Supersonic Pancake (Z-Axis Terminal Velocity) ---\n";
    reset();
    current_g[18][10][10].f[6] = 1000000000000000000; // 1 Quintillion moving DOWN
    int64_t s3 = get_total_mass();
    cout << "Dropping 1 Quintillion integer mass onto solid floor.\n";
    for(int i=0; i<200; i++) lbm_step();
    int64_t e3 = get_total_mass();
    cout << "Mass Pre: " << s3 << " | Post: " << e3;
    if(s3 != e3) cout << " [CRITICAL FAILURE: FLOOR BREACH]\n"; else cout << " [STABLE]\n";

    return 0;
}
