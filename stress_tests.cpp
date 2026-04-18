#include <iostream>
#include <cmath>
#include <iomanip>

using namespace std;

const int SIZE = 40;
struct Voxel { int64_t vx, vy, p; };
Voxel grid[SIZE][SIZE];
Voxel next_grid[SIZE][SIZE];

void reset_grid() {
    for(int y=0; y<SIZE; y++)
        for(int x=0; x<SIZE; x++)
            grid[y][x] = {0,0,0};
}

// The naive integer advection formula we used in the fast-prototype
void step() {
    for(int y=1; y<SIZE-1; y++) {
        for(int x=1; x<SIZE-1; x++) {
            // Integer Averaging
            next_grid[y][x].vx = (grid[y-1][x].vx + grid[y+1][x].vx + grid[y][x-1].vx + grid[y][x+1].vx) / 4;
            next_grid[y][x].vy = (grid[y-1][x].vy + grid[y+1][x].vy + grid[y][x-1].vy + grid[y][x+1].vy) / 4;
            
            // Pressure push
            next_grid[y][x].vx += (grid[y][x-1].p - grid[y][x+1].p)/2;
            next_grid[y][x].vy += (grid[y-1][x].p - grid[y+1][x].p)/2;
            
            // Density advection
            next_grid[y][x].p = grid[y][x].p - (grid[y][x+1].vx - grid[y][x-1].vx + grid[y+1][x].vy - grid[y-1][x].vy)/2;
        }
    }
    for(int y=1; y<SIZE-1; y++)
        for(int x=1; x<SIZE-1; x++)
            grid[y][x] = next_grid[y][x];
}

int64_t total_mass() {
    int64_t m = 0;
    for(int y=1;y<SIZE-1;y++) for(int x=1;x<SIZE-1;x++) m += grid[y][x].p;
    return m;
}

void test_1() {
    cout << "\n--- TEST 1: The Closed-Box Conservation Test ---\n";
    reset_grid();
    grid[20][20].p = 1000000; // Inject exactly 1 Million units of pressure mass
    cout << "Start Mass: " << total_mass() << "\n";
    for(int i=0; i<1000; i++) step();
    cout << "End Mass (After 1,000 steps): " << total_mass() << "\n";
    if (total_mass() != 1000000) cout << "[!] FAILED: Integer truncation caused energy leak! (Friction of Mathematics)\n";
    else cout << "[+] PASSED: Perfect Conservation achieved.\n";
}

void test_2() {
    cout << "\n--- TEST 2: Hemisphere Propagation (The 'Square Bubble' Problem) ---\n";
    reset_grid();
    grid[20][20].p = 1000000; 
    for(int i=0; i<6; i++) step();
    cout << "Cross-section of shockwave at Step 6:\n";
    for(int y=13; y<=27; y++) {
        for(int x=13; x<=27; x++) {
            if (grid[y][x].p > 100) cout << "██";
            else if (grid[y][x].p > 10) cout << "▒▒";
            else if (grid[y][x].p < -10) cout << "--"; // Vacuum
            else cout << "  ";
        }
        cout << "\n";
    }
    cout << "Observation: Do we see a perfect circular shockwave, or a 'square/diamond' bias?\n";
}

void test_3() {
    cout << "\n--- TEST 3: The Hurricane Vector (Integer Overflow Vulnerability) ---\n";
    reset_grid();
    long long huge_val = 9000000000000000000LL; // Approaching the 64-bit integer limit
    grid[20][20].vx = huge_val; 
    grid[20][20].vy = huge_val;
    cout << "Starting wind vector: " << grid[20][20].vx << "\n";
    step(); step();
    cout << "Vector after 2 steps: " << grid[20][20].vx << "\n";
    if (grid[20][20].vx < 0) cout << "[!] FAILED: Integer Overflow detected! The wind exceeded reality and turned negative.\n";
    else cout << "[+] PASSED: The grid bounds survived the Category 9 hurricane.\n";
}

int main() {
    cout << "===== DISCRETE FLUID DYNAMICS STRESS DIAGNOSTICS =====\n";
    test_1();
    test_2();
    test_3();
    return 0;
}
