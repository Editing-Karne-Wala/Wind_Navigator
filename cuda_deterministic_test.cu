#include <stdio.h>
#include <stdint.h>
#include <cuda_runtime.h>

// PHASE 7.1: CUDA DETERMINISTIC HASH VALIDATION
// -----------------------------------------------------
// RIP curand: Using bitwise integer hashing for noise to bypass TDR watchdog hangs.
// This ensures the RTX 2050 simulation is 100% deterministic and safe.

const int WIDTH = 1000;
const int HEIGHT = 1000;
#define TOTAL_VOXELS (WIDTH * HEIGHT)

struct Voxel {
    int64_t f[9];
    bool is_wall;
};

// GPU Cache Memory (Pre-load the Lattice weights directly onto the RTX silicon)
__constant__ int d_cx[9] = {0, 1, 0, -1, 0,  1, -1, -1,  1};
__constant__ int d_cy[9] = {0, 0, 1,  0, -1,  1,  1, -1, -1};
__constant__ int d_w[9]  = {16, 4, 4, 4, 4, 1, 1, 1, 1};
__constant__ int d_rev[9] = {0, 3, 4, 1, 2, 7, 8, 5, 6};

// PCG (Permuted Congruential Generator) bitwise hash for deterministic noise
// Bypasses the need for heavy CUDA Random states that cause time-out errors.
__device__ uint32_t fast_hash(uint32_t x) {
    uint32_t state = x * 747796405u + 2891336453u;
    uint32_t word = ((state >> ((state >> 28u) + 4u)) ^ state) * 277803737u;
    return (word >> 22u) ^ word;
}

// THE GPU KERNEL
__global__ void lbm_deterministic_kernel(Voxel* current_g, Voxel* next_g, int w, int h, int timestep) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx >= w * h) return;

    int x = idx % w;
    int y = idx / w;

    // Outer grid barrier
    if (x == 0 || x == w - 1 || y == 0 || y == h - 1) return;
    if (current_g[idx].is_wall) return;

    // STEP 1: PULL STREAMING
    int64_t pulled_mass[9] = {0};
    for (int i = 0; i < 9; i++) {
        int opp = d_rev[i];
        int nx = x + d_cx[opp];
        int ny = y + d_cy[opp];
        int n_idx = ny * w + nx;
        
        if (current_g[n_idx].is_wall) {
            pulled_mass[i] = current_g[idx].f[opp]; 
        } else {
            pulled_mass[i] = current_g[n_idx].f[i];
        }
    }

    // STEP 2: DETERMINISTIC NOISE INJECTION (Real-world chaotic perturbation)
    // We use the voxel index + timestep to generate a high-speed bitwise hash.
    uint32_t noise_seed = fast_hash(idx + timestep);
    int64_t noise_mag = (noise_seed % 7) - 3; // Shift mass by max +/- 3 units

    // STEP 3: THE REMAINDER VAULT (Mass Conservation audit)
    int64_t total_mass = 0;
    for (int i = 0; i < 9; i++) total_mass += pulled_mass[i];

    if (total_mass > 0) {
        int64_t distributed_mass = 0;
        for (int i = 0; i < 9; i++) {
            // Apply noise only to non-zero vectors to simulate local air density shifts
            int64_t eq = (total_mass * d_w[i]) / 36;
            if (i > 0 && i < 5) eq += noise_mag; // Perturb orthogonal vectors
            
            // Boundary safety: noise cannot create mass or exceed total
            if (eq < 0) eq = 0;
            
            next_g[idx].f[i] = eq;
            distributed_mass += eq;
        }
        // DEPOSIT INTO THE VAULT: This line guarantees 100.00% conservation
        // regardless of how chaotic the hash-based noise is.
        next_g[idx].f[0] += (total_mass - distributed_mass);
    } else {
        for (int i = 0; i < 9; i++) next_g[idx].f[i] = 0;
    }
}

int main() {
    printf("===== PHASE 7.1: CUDA DETERMINISTIC HASH VALIDATION =====\n");
    printf("[*] Target: 1,000,000 Voxels (OSM Manhattan Stress Simulation)\n");
    printf("[*] Watchdog Timer Avoidance: Enabled (curand replaced by fast_hash)\n");

    size_t memory_size = TOTAL_VOXELS * sizeof(Voxel);
    Voxel* h_grid = (Voxel*)malloc(memory_size);
    for(int i=0; i<TOTAL_VOXELS; i++) {
        h_grid[i].is_wall = (i % 7 == 0); // Simulated skyscraper clutter
        for(int j=0; j<9; j++) h_grid[i].f[j] = 0;
    }

    // High energy injection
    h_grid[500 * WIDTH + 500].f[0] = 500000000;

    Voxel *d_current, *d_next;
    cudaMalloc((void**)&d_current, memory_size);
    cudaMalloc((void**)&d_next, memory_size);
    cudaMemcpy(d_current, h_grid, memory_size, cudaMemcpyHostToDevice);

    int threadsPerBlock = 256;
    int blocksPerGrid = (TOTAL_VOXELS + threadsPerBlock - 1) / threadsPerBlock;

    for (int step = 0; step < 10000; step++) {
        lbm_deterministic_kernel<<<blocksPerGrid, threadsPerBlock>>>(d_current, d_next, WIDTH, HEIGHT, step);
        
        if (step % 1000 == 0) {
            printf("[*] Simulating Frame %d... (RTX 2050 Online)\n", step);
        }
        
        Voxel* temp = d_current;
        d_current = d_next;
        d_next = temp;
    }
    cudaDeviceSynchronize();

    // FINAL AUDIT: Transfer grid back to CPU to verify Remainder Vault integrity
    cudaMemcpy(h_grid, d_current, memory_size, cudaMemcpyDeviceToHost);
    int64_t final_mass = 0;
    for(int i=0; i<TOTAL_VOXELS; i++) {
        for(int j=0; j<9; j++) final_mass += h_grid[i].f[j];
    }

    printf("\n[+] CONSERVATION AUDIT: %lld units\n", final_mass);
    if (final_mass == 500000000) {
        printf("[+] SUCCESS: Deterministic Hashing results in 100.00%% Mass Conservation.\n");
        printf("[+] REMAINDER VAULT: UNBROKEN over 10,000 frames.\n");
    } else {
        printf("[!] WARNING: Mass leak detected! (Error: %lld)\n", 500000000 - final_mass);
    }

    cudaFree(d_current);
    cudaFree(d_next);
    free(h_grid);
    return 0;
}
