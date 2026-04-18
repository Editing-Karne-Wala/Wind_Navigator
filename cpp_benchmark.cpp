#include <iostream>
#include <vector>
#include <chrono>
#include <cmath>
#include <iomanip>
#include <cstdlib>

using namespace std;
using namespace std::chrono;

// Heretical parameters: 
// 50 MILLION discrete air voxels. 
// 10 Gigantic Time Steps (Fast-forwards).
const int NUM_PARTICLES = 50000000;
const int STEPS = 10;

// Thermal Updraft Target
const float THERMAL_X_F = 50000.0f;
const float THERMAL_Y_F = 50000.0f;
const int64_t THERMAL_X_I = 50000;
const int64_t THERMAL_Y_I = 50000;

struct ParticleF { float x, y; };
struct ParticleI { int64_t x, y; };

int main() {
    cout << "Allocating " << NUM_PARTICLES << " air voxels (Requires ~800MB RAM)..." << endl;
    
    vector<ParticleF> f_particles(NUM_PARTICLES);
    vector<ParticleI> i_particles(NUM_PARTICLES);
    
    // Seed and generate random starting positions
    for(int i = 0; i < NUM_PARTICLES; i++) {
        float rx = static_cast<float>(rand() % 100000);
        float ry = static_cast<float>(rand() % 100000);
        f_particles[i] = {rx, ry};
        i_particles[i] = {static_cast<int64_t>(rx), static_cast<int64_t>(ry)};
    }
    
    cout << "\n=== [TEST 1] CLASSICAL NAVIER-STOKES (Floats, Trig, Square Roots) ===" << endl;
    auto start_classical = high_resolution_clock::now();
    
    for (int s = 0; s < STEPS; s++) {
        for (auto& p : f_particles) {
            float dx = THERMAL_X_F - p.x;
            float dy = THERMAL_Y_F - p.y;
            
            // The Approximation Tax: Heavy FPU Operations
            float dist = sqrtf(dx*dx + dy*dy);
            
            if (dist > 1e-4f) {
                float angle = atan2f(dy, dx);
                // Taking HUGE 1,000 meter steps (normally throws CFD into chaos)
                p.x += cosf(angle) * 1000.0f; 
                p.y += sinf(angle) * 1000.0f;
            }
        }
    }
    
    auto end_classical = high_resolution_clock::now();
    double time_classical = duration_cast<duration<double>>(end_classical - start_classical).count();
    cout << "Time: " << fixed << setprecision(4) << time_classical << " seconds." << endl;
    
    
    cout << "\n=== [TEST 2] RATIONAL FLUID DYNAMICS (Exact Integers, ALU Only) ===" << endl;
    auto start_rational = high_resolution_clock::now();
    
    for (int s = 0; s < STEPS; s++) {
        for (auto& p : i_particles) {
            int64_t dx = THERMAL_X_I - p.x;
            int64_t dy = THERMAL_Y_I - p.y;
            
            // No Square Root needed. Using discrete proportions. 
            // Avoids FPU context switching completely.
            int64_t quad = dx*dx + dy*dy;
            if (quad > 0) {
                int64_t manhattan = abs(dx) + abs(dy);
                if (manhattan == 0) manhattan = 1;
                
                // Pure integer ALU division and multiplication
                p.x += (dx * 1000) / manhattan;
                p.y += (dy * 1000) / manhattan;
            }
        }
    }
    
    auto end_rational = high_resolution_clock::now();
    double time_rational = duration_cast<duration<double>>(end_rational - start_rational).count();
    cout << "Time: " << fixed << setprecision(4) << time_rational << " seconds." << endl;
    
    cout << "\n=== CONCLUSION ===" << endl;
    if (time_rational < time_classical) {
        cout << "Rational Engine was FAST. " << fixed << setprecision(2) << (time_classical / time_rational) << "x speedup!" << endl;
    } else {
         cout << "Classical Engine outperformed!" << endl;
    }

    return 0;
}
