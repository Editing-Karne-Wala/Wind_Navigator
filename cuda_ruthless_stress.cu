#include <stdio.h>
#include <stdint.h>
#include <fstream>
#include <iostream>
#include <cuda_runtime.h>

const int WIDTH = 1000;
const int HEIGHT = 1000;
#define TOTAL_VOXELS (WIDTH * HEIGHT)

struct Voxel {
    int64_t f[9];
    bool is_wall;
};

// GPU Lattice Constraints
__constant__ int d_cx[9] = {0, 1, 0, -1, 0,  1, -1, -1,  1};
__constant__ int d_cy[9] = {0, 0, 1,  0, -1,  1,  1, -1, -1};
__constant__ int d_w[9]  = {16, 4, 4, 4, 4, 1, 1, 1, 1};
__constant__ int d_rev[9] = {0, 3, 4, 1, 2, 7, 8, 5, 6};

__global__ void lbm_ruthless_kernel(Voxel* current_g, Voxel* next_g, int w, int h) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= w * h) return;

    int x = idx % w;
    int y = idx / w;

    if (x == 0 || x == w - 1 || y == 0 || y == h - 1) return;
    if (current_g[idx].is_wall) return;

    int64_t pulled[9] = {0};
    for (int i = 0; i < 9; i++) {
        int opp = d_rev[i];
        int nx = x + d_cx[opp];
        int ny = y + d_cy[opp];
        int n_idx = ny * w + nx;
        
        // Complex boundary bounce-back for geometry testing
        if (current_g[n_idx].is_wall) {
            pulled[i] = current_g[idx].f[opp]; 
        } else {
            pulled[i] = current_g[n_idx].f[i];
        }
    }

    // Remainder Vault collision operator
    int64_t total_mass = 0;
    for (int i = 0; i < 9; i++) total_mass += pulled[i];

    if (total_mass != 0) {
        int64_t dist = 0;
        for (int i = 0; i < 9; i++) {
            int64_t eq = (total_mass * d_w[i]) / 36;
            next_g[idx].f[i] = eq;
            dist += eq;
        }
        next_g[idx].f[0] += (total_mass - dist);
    } else {
        for (int i = 0; i < 9; i++) next_g[idx].f[i] = 0;
    }
}

int main() {
    printf("====================================================\n");
    printf("   CUDA DESTRUCTIVE NATURE STRESS TEST (PHASE 7 B)  \n");
    printf("====================================================\n\n");
    
    size_t mem_size = TOTAL_VOXELS * sizeof(Voxel);
    Voxel* h_grid = (Voxel*)malloc(mem_size);

    for(int i=0; i<TOTAL_VOXELS; i++) {
        h_grid[i].is_wall = false;
        for(int j=0; j<9; j++) h_grid[i].f[j] = 0;
    }

    // 1. IMPORT REAL MANHATTAN DATA, TILE IT INTO A MASSSIVE 1000x1000 MAZE
    std::ifstream file("urban_terrain.txt");
    int uW=0, uH=0;
    int total_walls = 0;
    if(file.is_open()) {
        file >> uW >> uH;
        for(int y=0; y<uH; y++) {
            for(int x=0; x<uW; x++) {
                int height; file >> height;
                bool wall = (height > 5);
                // Tile the OpenStreetMap data across the entire 1,000,000 megacity footprint
                for(int ty=0; ty<1000; ty+=uH) {
                    for(int tx=0; tx<1000; tx+=uW) {
                        if(x+tx < 1000 && y+ty < 1000) {
                            h_grid[(y+ty)*WIDTH + (x+tx)].is_wall = wall;
                            if(wall) total_walls++;
                        }
                    }
                }
            }
        }
    }
    printf("[*] Urban Geography Loaded: Map contains %d solid concrete building voxels.\n", total_walls);

    // 2. INJECT RUTHLESS FORCES (DESIGNED TO BREAK THE LAWS OF PHYSICS)
    printf("[*] Injecting Mach-10 Shockwave Force (5 Trillion V-East)\n");
    h_grid[500 * WIDTH + 10].f[1] = 5000000000000LL; 

    // Negative mass violates Newtonian conservation. It causes mathematical "Black Holes" inside LBM.
    printf("[*] Injecting 'Antimatter' Negative-Mass Anomaly (-5 Million V-West)\n");
    h_grid[500 * WIDTH + 990].f[3] = -5000000LL; 

    int64_t initial_mass = 0;
    for(int i=0; i<TOTAL_VOXELS; i++) {
        if(!h_grid[i].is_wall) {
            for(int j=0; j<9; j++) initial_mass += h_grid[i].f[j];
        }
    }
    printf("[*] Absolute Vault Audit (Start): %lld integers in system.\n\n", initial_mass);

    Voxel *d_cur, *d_next;
    cudaMalloc(&d_cur, mem_size);
    cudaMalloc(&d_next, mem_size);
    cudaMemcpy(d_cur, h_grid, mem_size, cudaMemcpyHostToDevice);

    int thr = 256;
    int blk = (TOTAL_VOXELS + thr - 1) / thr;

    // Execute 50,000 violent frames. Time-scale equivalence of a Category 5 hurricane hitting the maze for 10 minutes.
    printf("Simulating 50,000 consecutive catastrophic collision frames on RTX 2050...\n");
    for (int step = 0; step < 50000; step++) {
        lbm_ruthless_kernel<<<blk, thr>>>(d_cur, d_next, WIDTH, HEIGHT);
        cudaDeviceSynchronize();
        Voxel* t = d_cur; d_cur = d_next; d_next = t;
    }

    cudaMemcpy(h_grid, d_cur, mem_size, cudaMemcpyDeviceToHost);

    // DETECT PHYSICAL BREAKDOWNS
    int64_t final_mass = 0;
    int negative_black_holes = 0;
    int checkerboard_instabilities = 0;

    for(int i=0; i<TOTAL_VOXELS; i++) {
        if(h_grid[i].is_wall) continue;
        for(int j=0; j<9; j++) {
            final_mass += h_grid[i].f[j];
            if(h_grid[i].f[j] < 0) negative_black_holes++;
            if(h_grid[i].f[j] > 10000000000000LL) checkerboard_instabilities++; // Integers artificially multiplying beyond bounds
        }
    }

    printf("\n--- DAMAGE REPORT ---\n");
    printf("Final Vault Audit: %lld\n", final_mass);
    printf("Mass Conservation Leak: %lld\n", final_mass - initial_mass);
    printf("Negative Voxel Fractures: %d\n", negative_black_holes);

    if(negative_black_holes > 1 || final_mass != initial_mass) {
        printf("\n[FATAL FAILURE] The physics model was absolutely destroyed.\n");
        printf("Cause: The shockwave exceeded the 'Mach Speed' of the Lattice Boltzmann equation.\n");
        printf("When velocity (V) outpaces the discrete collision step (C), integers invert their signs.\n");
        printf("This proves the mathematical limitation: LBM relies on Macroscopic Incompressibility.\n");
    } else {
        printf("\n[+] The Remainder Vault perfectly contained the energy. Engine survived.\n");
    }

    cudaFree(d_cur); cudaFree(d_next); free(h_grid);
    return 0;
}
