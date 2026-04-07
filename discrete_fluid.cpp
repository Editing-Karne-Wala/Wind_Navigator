#include <iostream>
#include <fstream>
#include <vector>
#include <chrono>
#include <iomanip>

using namespace std;
using namespace std::chrono;

const int WIDTH = 60;
const int HEIGHT = 20;
const int STEPS = 100;
const int64_t SCALE = 1000; 

struct Voxel {
    int64_t vx, vy;
    int64_t pressure;
    bool is_wall;
};

Voxel grid[HEIGHT][WIDTH];
Voxel next_grid[HEIGHT][WIDTH];
int64_t GLOBAL_VX = 0;
int64_t GLOBAL_VY = 0;

void init_grid() {
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            grid[y][x] = {0, 0, 0, false};
            
            // Build the Manhattan Skyscraper complex
            if (x >= 25 && x <= 30 && y >= 5 && y <= 15) {
                grid[y][x].is_wall = true;
            }
            if (x >= 40 && x <= 45 && y >= 10 && y <= 18) {
                grid[y][x].is_wall = true;
            }
        }
    }
}

void step_fluid() {
    // Inject REAL-WORLD Weather Data
    // Wind is pushing East (vx > 0) and South (vy < 0) according to live METAR today
    for (int y = 0; y < HEIGHT; y++) {
        if (!grid[y][0].is_wall) {
            grid[y][0].vx = GLOBAL_VX; 
            grid[y][0].vy = GLOBAL_VY; 
            grid[y][0].pressure = 10 * SCALE;
        }
    }
    for (int x = 0; x < WIDTH; x++) {
        if (!grid[0][x].is_wall) {
            grid[0][x].vx = GLOBAL_VX;
            grid[0][x].vy = GLOBAL_VY;
            grid[0][x].pressure = 10 * SCALE;
        }
    }

    for (int y = 1; y < HEIGHT - 1; y++) {
        for (int x = 1; x < WIDTH - 1; x++) {
            if (grid[y][x].is_wall) {
                next_grid[y][x] = grid[y][x];
                continue;
            }

            int64_t avg_vx = (grid[y-1][x].vx + grid[y+1][x].vx + grid[y][x-1].vx + grid[y][x+1].vx) / 4;
            int64_t avg_vy = (grid[y-1][x].vy + grid[y+1][x].vy + grid[y][x-1].vy + grid[y][x+1].vy) / 4;
            int64_t avg_p  = (grid[y-1][x].pressure + grid[y+1][x].pressure + grid[y][x-1].pressure + grid[y][x+1].pressure) / 4;

            int64_t grad_px = (grid[y][x-1].pressure - grid[y][x+1].pressure) / 2;
            int64_t grad_py = (grid[y-1][x].pressure - grid[y+1][x].pressure) / 2;

            next_grid[y][x].vx = avg_vx + grad_px / 10;
            next_grid[y][x].vy = avg_vy + grad_py / 10;
            next_grid[y][x].pressure = avg_p - (grid[y][x+1].vx - grid[y][x-1].vx + grid[y+1][x].vy - grid[y-1][x].vy) / 10;
            
            // Boundary mechanics (Updrafts generated purely by integer collision)
            if (grid[y][x+1].is_wall && next_grid[y][x].vx > 0) next_grid[y][x].vy -= abs(next_grid[y][x].vx) / 2;
            if (grid[y+1][x].is_wall && next_grid[y][x].vy > 0) next_grid[y][x].vx -= abs(next_grid[y][x].vy) / 2;
        }
    }

    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            grid[y][x] = next_grid[y][x];
        }
    }
}

void print_wind() {
    cout << "\n=== MANHATTAN LIVE WEATHER SIMULATION (INTEGER ENGINE) ===\n";
    cout << "Input Vectors -> Vx: " << GLOBAL_VX << " | Vy: " << GLOBAL_VY << "\n";
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            if (grid[y][x].is_wall) {
                cout << "██"; 
            } else {
                int64_t speed = abs(grid[y][x].vx) + abs(grid[y][x].vy);
                if (grid[y][x].vy < -1000) cout << "↑ "; // Strong North/Updraft
                else if (grid[y][x].vy > 1000) cout << "↓ "; // Strong South/Downdraft
                else if (grid[y][x].vx > 1000) cout << "→ "; // Strong East
                else if (speed > 500) cout << "/ "; // Diagonal shear
                else cout << ". "; // Calm
            }
        }
        cout << "\n";
    }
}

int main() {
    ifstream infile("real_wind_input.txt");
    if (infile.is_open()) {
        infile >> GLOBAL_VX >> GLOBAL_VY;
        infile.close();
    } else {
        cout << "Failed to load real weather data!\n";
        return 1;
    }

    init_grid();
    
    auto start = high_resolution_clock::now();
    for (int i = 0; i < STEPS; i++) {
        step_fluid();
    }
    auto end = high_resolution_clock::now();
    
    print_wind();
    
    cout << "\n[METRICS]\n";
    cout << "Simulated Time Steps: " << STEPS << " (Forward Prediction Mapping)\n";
    cout << "Calculation Time: " << fixed << setprecision(5) << duration_cast<duration<double>>(end - start).count() << " seconds.\n";
    return 0;
}
