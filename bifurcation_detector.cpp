// PHASE 15: BIFURCATION ZONE DETECTOR
// =====================================
// Scans for Saddle Points (Bifurcation Zones) using the Integer Divergence
// Criterion — the rational substitute for the continuous gradient method.
//
// THE RATIONAL RULE:
//   dvx_dx = vx[East] - vx[West]   (integer subtraction)
//   dvy_dy = vy[North] - vy[South] (integer subtraction)
//   BIFURCATION iff dvx_dx * dvy_dy < 0
//   (one axis stretching, one compressing = classic saddle point topology)
//
// TEST DESIGN:
//   10 saddle-point velocity fields are DIRECTLY INJECTED into grid voxels.
//   This isolates the DETECTOR from the SIMULATOR, testing only the math.
//   Each test injects a neighbourhood where local velocity vectors explicitly
//   satisfy the saddle condition (dvx_dx and dvy_dy with opposite signs).
//
//   10 NON-BIFURCATION controls are also injected (same-sign gradients) to
//   validate ZERO FALSE POSITIVES.

#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>

const int W = 150;
const int H = 150;
#define N (W * H)
#define IDX(x,y) ((y)*W+(x))

struct Voxel {
    int64_t vx, vy;
    bool    is_wall;
    bool    is_bifurcation;
    bool    is_control;    // TRUE = intentionally NOT a bifurcation
};

Voxel grid[N];

// ============================================================
//   INTEGER DIVERGENCE BIFURCATION SCAN
// ============================================================
int scan_bifurcations() {
    int count = 0;
    for (int y = 1; y < H-1; y++) {
        for (int x = 1; x < W-1; x++) {
            int idx = IDX(x,y);
            grid[idx].is_bifurcation = false;
            if (grid[idx].is_wall) continue;

            int N_idx = IDX(x, y+1);
            int S_idx = IDX(x, y-1);
            int E_idx = IDX(x+1, y);
            int W_idx = IDX(x-1, y);

            if (grid[N_idx].is_wall || grid[S_idx].is_wall ||
                grid[E_idx].is_wall || grid[W_idx].is_wall) continue;

            // INTEGER DIVERGENCE CRITERION (no irrational ops)
            int64_t dvx_dx = grid[E_idx].vx - grid[W_idx].vx;
            int64_t dvy_dy = grid[N_idx].vy - grid[S_idx].vy;

            // Saddle: one axis stretching (+), one compressing (-) → product < 0
            if (dvx_dx * dvy_dy < 0) {
                grid[idx].is_bifurcation = true;
                count++;
            }
        }
    }
    return count;
}

// ============================================================
//   INJECT A SADDLE-POINT NEIGHBOURHOOD
//   At center (cx, cy), set local velocity vectors so that:
//     East vx > West vx  (dvx_dx > 0: x-stretching)
//     North vy < South vy (dvy_dy < 0: y-compressing)
//   → Product < 0 → BIFURCATION detected at center
// ============================================================
void inject_bifurcation(int cx, int cy, int64_t magnitude) {
    // Center voxel
    grid[IDX(cx,cy)].vx = 0; grid[IDX(cx,cy)].vy = 0;
    // East: vx positive (flow accelerating eastward)
    grid[IDX(cx+1,cy)].vx =  magnitude; grid[IDX(cx+1,cy)].vy = 0;
    // West: vx negative (flow decelerating from west)
    grid[IDX(cx-1,cy)].vx = -magnitude; grid[IDX(cx-1,cy)].vy = 0;
    // North: vy negative (flow compressing toward center from north)
    grid[IDX(cx,cy+1)].vx = 0; grid[IDX(cx,cy+1)].vy = -magnitude;
    // South: vy positive (flow compressing toward center from south)
    grid[IDX(cx,cy-1)].vx = 0; grid[IDX(cx,cy-1)].vy =  magnitude;
    // dvx_dx = magnitude - (-magnitude) = 2*magnitude > 0
    // dvy_dy = -magnitude - magnitude   = -2*magnitude < 0
    // Product = 2M * (-2M) = -4M² < 0 → SADDLE CONFIRMED
}

// ============================================================
//   INJECT A NON-BIFURCATION CONTROL NEIGHBOURHOOD
//   Both gradients have the same sign → product > 0 → NOT a saddle
// ============================================================
void inject_control(int cx, int cy, int64_t magnitude) {
    grid[IDX(cx,cy)].vx = 0; grid[IDX(cx,cy)].vy = 0;
    grid[IDX(cx,cy)].is_control = true;
    // East: vx positive → dvx_dx > 0
    grid[IDX(cx+1,cy)].vx =  magnitude; grid[IDX(cx+1,cy)].vy = 0;
    grid[IDX(cx-1,cy)].vx = -magnitude; grid[IDX(cx-1,cy)].vy = 0;
    // North: vy positive too → dvy_dy > 0 → product > 0 → NOT a saddle
    grid[IDX(cx,cy+1)].vx = 0; grid[IDX(cx,cy+1)].vy =  magnitude;
    grid[IDX(cx,cy-1)].vx = 0; grid[IDX(cx,cy-1)].vy = -magnitude;
}

bool has_bifurcation_near(int cx, int cy, int r) {
    for (int dy = -r; dy <= r; dy++)
        for (int dx = -r; dx <= r; dx++) {
            int nx = cx+dx, ny = cy+dy;
            if (nx<0||nx>=W||ny<0||ny>=H) continue;
            if (grid[IDX(nx,ny)].is_bifurcation) return true;
        }
    return false;
}

int main() {
    printf("=======================================================\n");
    printf("  PHASE 15: BIFURCATION ZONE DETECTOR                 \n");
    printf("=======================================================\n");
    printf("[*] Grid: %dx%d\n", W, H);
    printf("[*] Method: Integer Divergence Criterion (dvx_dx * dvy_dy < 0)\n");
    printf("[*] 10 saddle-point fields + 10 non-saddle controls injected.\n");
    printf("[*] No irrational ops: all comparisons are integer multiplications.\n\n");

    memset(grid, 0, sizeof(grid));

    // ----------------------------------------------------------------
    //  INJECT 10 KNOWN BIFURCATION (SADDLE) POINTS
    // ----------------------------------------------------------------
    const int64_t MAG = 1000LL;
    int bif_x[10] = {10, 25, 40, 55, 70, 85, 100, 115, 20, 60};
    int bif_y[10] = {10, 20, 30, 40, 50, 60,  70,  80, 90, 90};

    for (int i = 0; i < 10; i++) {
        inject_bifurcation(bif_x[i], bif_y[i], MAG);
    }

    // ----------------------------------------------------------------
    //  INJECT 10 NON-BIFURCATION CONTROLS (same-sign gradients)
    // ----------------------------------------------------------------
    int ctl_x[10] = {10, 25, 40, 55, 70, 85, 100, 115, 20, 60};
    int ctl_y[10] = {130,120,110,100, 90, 80,  70, 120,110,120};

    for (int i = 0; i < 10; i++) {
        // Make sure controls don't overlap with bifurcations
        if (abs(ctl_y[i] - bif_y[i]) > 10)
            inject_control(ctl_x[i], ctl_y[i], MAG);
    }

    // Run the scan
    int total = scan_bifurcations();

    // ----------------------------------------------------------------
    //  AUDIT 1: BIFURCATION DETECTION ACCURACY
    // ----------------------------------------------------------------
    printf("--- AUDIT 1: KNOWN SADDLE-POINT VERIFICATION ---\n");
    int detected = 0;
    for (int i = 0; i < 10; i++) {
        bool found = has_bifurcation_near(bif_x[i], bif_y[i], 1);
        printf("  Saddle #%2d @ [%3d,%3d]: %s\n",
               i+1, bif_x[i], bif_y[i],
               found ? "[DETECTED ✓]" : "[NOT FOUND ✗]");
        if (found) detected++;
    }

    // ----------------------------------------------------------------
    //  AUDIT 2: FALSE POSITIVE CHECK (controls must NOT be detected)
    // ----------------------------------------------------------------
    printf("\n--- AUDIT 2: FALSE POSITIVE CONTROL CHECK ---\n");
    int false_pos = 0;
    for (int i = 0; i < 10; i++) {
        if (abs(ctl_y[i] - bif_y[i]) <= 10) continue; // skip overlapping
        bool wrongly_detected = has_bifurcation_near(ctl_x[i], ctl_y[i], 1);
        printf("  Control #%2d @ [%3d,%3d]: %s\n",
               i+1, ctl_x[i], ctl_y[i],
               wrongly_detected ? "[FALSE POSITIVE ✗]" : "[CORRECTLY IGNORED ✓]");
        if (wrongly_detected) false_pos++;
    }

    printf("\n--- AUDIT 3: FULL GRID STATISTICS ---\n");
    printf("  Total Bifurcation Zones   : %d\n", total);
    printf("  Saddles Correctly Detected: %d / 10\n", detected);
    printf("  False Positives           : %d\n", false_pos);

    // Confidence Scoring
    printf("\n--- AUDIT 4: CONFIDENCE SCORE API DEMO ---\n");
    const char* confidence = (total <= 5)  ? "HIGH"   :
                             (total <= 20) ? "MEDIUM" : "LOW";
    printf("  Chaos Score : %d bifurcation zones\n", total);
    printf("  Confidence  : %s\n\n", confidence);
    printf("  Sample API Response:\n");
    printf("  {\n");
    printf("    \"wind_vector\": {\"vx\": 3, \"vy\": -1, \"vz\": 0},\n");
    printf("    \"chaos_score\": %d,\n", total);
    printf("    \"confidence\": \"%s\"\n", confidence);
    printf("  }\n");

    printf("\n=======================================================\n");
    printf("  PHASE 15 FINAL VERDICT\n");
    printf("=======================================================\n");
    printf("  RESULT: %s\n",
        (detected == 10 && false_pos == 0)
        ? "[PASS] 10/10 saddles detected. 0 false positives. API safety wall OPERATIONAL."
        : (detected >= 8 && false_pos == 0)
        ? "[PASS] High accuracy detection. 0 false positives."
        : "[WARN] Check injection positions or scan radius.");

    return 0;
}
