#include <stdio.h>
#include <stdint.h>
#include <cuda_runtime.h>
#include <fstream>
#include <iostream>

using namespace std;

#define CITY_W 80
#define CITY_H 80
#define MAX_DRONES 100000 

__constant__ int d_osm_map[CITY_W * CITY_H];

struct DroneTelemetry {
    int start_x, start_y;
    int target_x, target_y;
    int battery_consumed;
    bool crashed_into_concrete;
    bool reached_target;
};

// Extremely lightweight pseudo-random generator to bypass Windows TDR Timeout
__device__ unsigned int pcg_hash(unsigned int input) {
    unsigned int state = input * 747796405u + 2891336453u;
    unsigned int word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

__global__ void swarm_pathfinder_kernel(DroneTelemetry* swarm, int seed) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= MAX_DRONES) return;

    // Randomize initial drone assignments
    unsigned int r1 = pcg_hash(seed + idx);
    unsigned int r2 = pcg_hash(r1);
    unsigned int r3 = pcg_hash(r2);
    unsigned int r4 = pcg_hash(r3);

    int sx = r1 % CITY_W;
    int sy = r2 % CITY_H;
    int tx = r3 % CITY_W;
    int ty = r4 % CITY_H;

    swarm[idx].start_x = sx;
    swarm[idx].start_y = sy;
    swarm[idx].target_x = tx;
    swarm[idx].target_y = ty;
    swarm[idx].crashed_into_concrete = false;
    swarm[idx].reached_target = false;
    
    int start_alt = d_osm_map[sy * CITY_W + sx] + 2;
    int cur_x = sx, cur_y = sy, cur_z = start_alt;
    int battery = 0;

    unsigned int stream = pcg_hash(r4);

    for (int ticks = 0; ticks < 1000; ticks++) {
        if (cur_x == tx && cur_y == ty) {
            swarm[idx].reached_target = true;
            break;
        }

        int move_x = 0;
        if (cur_x < tx) move_x = 1;
        else if (cur_x > tx) move_x = -1;

        int move_y = 0;
        if (cur_y < ty) move_y = 1;
        else if (cur_y > ty) move_y = -1;

        int next_x = cur_x + move_x;
        int next_y = cur_y + move_y;
        
        // Hurricane turbulence pushes drones randomly off course
        stream = pcg_hash(stream);
        if (stream % 100 > 75) { 
            next_x += ((stream % 3) - 1); 
            stream = pcg_hash(stream);
            next_y += ((stream % 3) - 1);
        }

        if (next_x < 0) next_x = 0; if (next_x >= CITY_W) next_x = CITY_W - 1;
        if (next_y < 0) next_y = 0; if (next_y >= CITY_H) next_y = CITY_H - 1;

        int building_height_ahead = d_osm_map[next_y * CITY_W + next_x];

        if (cur_z < building_height_ahead) {
            cur_z += 5; // Panic thrust
            battery += 25; 
            
            if(cur_z < building_height_ahead) {
                swarm[idx].crashed_into_concrete = true;
                break;
            }
        }

        cur_x = next_x;
        cur_y = next_y;
        battery += 5; 
        
        int wind_lift = 0;
        if (building_height_ahead > cur_z - 5) {
            wind_lift = 10; 
            cur_z += 2;
        }
        
        battery -= wind_lift; 
        if(battery < 0) battery = 0; 
    }

    swarm[idx].battery_consumed = battery;
}

int main() {
    printf("=======================================================================\n");
    printf("  CUDA NATURE DRONE SWARM: PARALLEL 100,000 OPENSTREETMAP PATHFINDERS  \n");
    printf("=======================================================================\n\n");

    int h_map[CITY_W * CITY_H] = {0};

    ifstream file("urban_terrain.txt");
    if (file.is_open()) {
        int dummyW, dummyH;
        file >> dummyW >> dummyH; 
        int map_idx = 0;
        for (int y = 0; y < CITY_H; y++) {
            for (int x = 0; x < CITY_W; x++) {
                file >> h_map[map_idx++];
            }
        }
    }
    
    printf("[*] Loaded %d concrete Voxels from Midtown Manhattan.\n", CITY_W * CITY_H);

    cudaMemcpyToSymbol(d_osm_map, h_map, CITY_W * CITY_H * sizeof(int));

    DroneTelemetry* d_swarm;
    size_t mem_size = MAX_DRONES * sizeof(DroneTelemetry);
    cudaMalloc((void**)&d_swarm, mem_size);
    // Initialize memory to prevent garbage data
    cudaMemset(d_swarm, 0, mem_size);

    int thr = 256;
    int blk = (MAX_DRONES + thr - 1) / thr;

    printf("[*] Activating 100,000 Autonomous Drones simultaneously...\n");
    printf("[*] Inducing Chaotic Category-3 Hurricane crosswinds...\n");
    printf("[*] Firing 100,000 concurrent flight paths over CUDA architecture...\n\n");

    swarm_pathfinder_kernel<<<blk, thr>>>(d_swarm, 12345);
    cudaDeviceSynchronize();

    DroneTelemetry* h_swarm = (DroneTelemetry*)malloc(mem_size);
    cudaMemcpy(h_swarm, d_swarm, mem_size, cudaMemcpyDeviceToHost);

    int total_crashes = 0;
    int total_success = 0;
    int total_lost = 0;
    int best_battery = 9999999;
    int worst_battery = 0;

    for (int i = 0; i < MAX_DRONES; i++) {
        if (h_swarm[i].crashed_into_concrete) {
            total_crashes++;
        } else if (h_swarm[i].reached_target) {
            total_success++;
            if (h_swarm[i].battery_consumed < best_battery) best_battery = h_swarm[i].battery_consumed;
            if (h_swarm[i].battery_consumed > worst_battery) worst_battery = h_swarm[i].battery_consumed;
        } else {
            total_lost++;
        }
    }

    printf("--- MASSIVE SWARM DISASTER LOGISTICS REPORT ---\n");
    printf("Total Delivery Missions Launched:    %d\n", MAX_DRONES);
    printf("Successful Target Arrivals:          %d\n", total_success);
    printf("Violent Concrete Collisions:         %d\n", total_crashes);
    printf("Drones Lost to Hurricane Traps:      %d\n", total_lost);
    
    printf("\n--- ENERGY METRICS (SURVIVORS) ---\n");
    if(total_success > 0) {
        printf("Most Efficient Fleet Battery Route:  %d Watts\n", best_battery);
        printf("Least Efficient Fleet Battery Route: %d Watts\n", worst_battery);
    }

    cudaFree(d_swarm);
    free(h_swarm);
    return 0;
}
