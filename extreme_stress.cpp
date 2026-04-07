#include <iostream>
#include <vector>
#include <iomanip>

using namespace std;

const int WIDTH = 30;
const int HEIGHT = 15;

const int cx[9] = {0, 1, 0, -1, 0,  1, -1, -1,  1};
const int cy[9] = {0, 0, 1,  0, -1,  1,  1, -1, -1};
const int w[9] = {16, 4, 4, 4, 4, 1, 1, 1, 1};
const int reverse_dir[9] = {0, 3, 4, 1, 2, 7, 8, 5, 6};

struct Voxel { int64_t f[9]; bool is_wall; };

Voxel grid1[HEIGHT][WIDTH];
Voxel grid2[HEIGHT][WIDTH];
Voxel (*current_g)[WIDTH] = grid1;
Voxel (*next_g)[WIDTH] = grid2;

void reset_grid() {
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            for (int i = 0; i < 9; i++) {
                current_g[y][x].f[i] = 0;
                next_g[y][x].f[i] = 0;
            }
            if (x == 0 || x == WIDTH - 1 || y == 0 || y == HEIGHT - 1) {
                current_g[y][x].is_wall = true;
                next_g[y][x].is_wall = true;
            } else {
                current_g[y][x].is_wall = false;
                next_g[y][x].is_wall = false;
            }
        }
    }
}

void lbm_step() {
    for (int y = 1; y < HEIGHT - 1; y++)
        for (int x = 1; x < WIDTH - 1; x++)
            for(int i=0; i<9; i++) next_g[y][x].f[i] = 0; 

    // Streaming
    for (int y = 1; y < HEIGHT - 1; y++) {
        for (int x = 1; x < WIDTH - 1; x++) {
            if (current_g[y][x].is_wall) continue;
            for (int i = 0; i < 9; i++) {
                int64_t mass = current_g[y][x].f[i];
                if (mass == 0) continue;
                int nx = x + cx[i];
                int ny = y + cy[i];
                if (current_g[ny][nx].is_wall) next_g[y][x].f[reverse_dir[i]] += mass;
                else next_g[ny][nx].f[i] += mass;
            }
        }
    }

    // Collision & Remainder Vault
    for (int y = 1; y < HEIGHT - 1; y++) {
        for (int x = 1; x < WIDTH - 1; x++) {
            if (next_g[y][x].is_wall) continue;

            int64_t total_mass = 0;
            for (int i=0; i<9; i++) total_mass += next_g[y][x].f[i];

            if (total_mass != 0) { // Can handle negative now for checking
                int64_t distributed_mass = 0;
                for (int i = 0; i < 9; i++) {
                    int64_t eq = (total_mass * w[i]) / 36; 
                    next_g[y][x].f[i] = eq; 
                    distributed_mass += eq;
                }
                int64_t remainder = total_mass - distributed_mass;
                next_g[y][x].f[0] += remainder; 
            }
        }
    }

    Voxel (*temp)[WIDTH] = current_g;
    current_g = next_g;
    next_g = temp;
}

int64_t get_total_mass() {
    int64_t m = 0;
    for (int y = 1; y < HEIGHT - 1; y++)
        for (int x = 1; x < WIDTH - 1; x++)
            for (int i = 0; i < 9; i++) m += current_g[y][x].f[i];
    return m;
}

void print_status(int step, int64_t start_mass) {
    int64_t current = get_total_mass();
    cout << "Step " << step << " | Mass: " << current;
    if (current != start_mass) cout << " [CRITICAL FAILURE: MASS LEAK DETECTED]\n";
    else cout << " [STABLE]\n";
}

int main() {
    cout << "===== PROJECT BLACKBOX: CRITICAL STRESS DESTRUCTION =====\n\n";

    // TEST 1: The Zero-Kelvin Antimatter Bomb (Negative Mass)
    // What if the environment triggers a hard negative pressure?
    cout << "--- TEST 1: The Antimatter Void (Negative Mass Injection) ---\n";
    reset_grid();
    current_g[7][15].f[0] = -1000000; // Inject negative mass
    int64_t start1 = get_total_mass();
    for (int i = 1; i <= 5; i++) lbm_step();
    print_status(5, start1);
    
    // TEST 2: The Mach Infinity ALU Crush (Multiplication Overflow)
    // equation: eq = (total_mass * 16) / 36. 
    // If total_mass > INT64_MAX / 16, the multiplication overflows BEFORE the division.
    cout << "\n--- TEST 2: The Mach-Infinity ALU Crush (Arithmetic Overflow) ---\n";
    reset_grid();
    int64_t dangerously_high = 900000000000000000; // 900 Quadrillion
    current_g[7][15].f[1] = dangerously_high;
    current_g[7][15].f[2] = dangerously_high; // Total mass will be 1.8 Quintillion
    int64_t start2 = get_total_mass();
    cout << "Initial Mass: " << start2 << "\n";
    lbm_step();
    int64_t mass_after = get_total_mass();
    cout << "Mass post-collision: " << mass_after << "\n";
    if (mass_after != start2) cout << "CRASH: Engine shattered under integer bounds.\n";

    // TEST 3: The Micro-Cavitation Trap (Modulo Entropy Freeze)
    cout << "\n--- TEST 3: The Micro-Cavitation Trap (Low integer freeze) ---\n";
    reset_grid();
    // Build a tiny 1x1 cage inside the grid
    current_g[6][15].is_wall = true; next_g[6][15].is_wall = true;
    current_g[8][15].is_wall = true; next_g[8][15].is_wall = true;
    current_g[7][14].is_wall = true; next_g[7][14].is_wall = true;
    current_g[7][16].is_wall = true; next_g[7][16].is_wall = true;
    current_g[6][14].is_wall = true; next_g[6][14].is_wall = true;
    current_g[6][16].is_wall = true; next_g[6][16].is_wall = true;
    current_g[8][14].is_wall = true; next_g[8][14].is_wall = true;
    current_g[8][16].is_wall = true; next_g[8][16].is_wall = true;
    
    current_g[7][15].f[0] = 35; // Mass is exactly 35. Too small to distribute to 36 weights cleanly.
    int64_t start3 = get_total_mass();
    cout << "Injecting 35 units of mass into a sealed 1x1 grid cage...\n";
    for (int i = 0; i < 50; i++) lbm_step();
    print_status(50, start3);
    cout << "Inspect Voxel[0] Vector Center: " << current_g[7][15].f[0] << "\n";
    if (current_g[7][15].f[0] == 35) cout << "BUG: Sub-Quantum freezing detected. Physics stopped due to low integer resolution.\n";

    return 0;
}
