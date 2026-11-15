/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef AFM_GWYDDION_H
#define AFM_GWYDDION_H

#if defined(_WIN32)
#define AFM_GWY_API __declspec(dllexport)
#else
#define AFM_GWY_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

enum {
    AFM_GWY_OK = 0,
    AFM_GWY_ARGUMENT = 1,
    AFM_GWY_REFERENCE = 2,
    AFM_GWY_NONFINITE = 3,
    AFM_GWY_FAILURE = 4
};

/* Method numbers intentionally match the reference harness, not Gwyddion's UI enum. */
enum {
    AFM_GWY_MEAN = 0,
    AFM_GWY_MEDIAN = 1,
    AFM_GWY_MEDIAN_DIFFERENCE = 2,
    AFM_GWY_MODUS = 3,
    AFM_GWY_MATCHING = 4,
    AFM_GWY_TRIMMED_MEAN = 5,
    AFM_GWY_TRIMMED_DIFFERENCE = 6,
    AFM_GWY_FACET_TILT = 7,
    AFM_GWY_POLYNOMIAL = 8
};

AFM_GWY_API const char *afm_gwyddion_version(void);
AFM_GWY_API int afm_gwyddion_abi_version(void);
/* Call once on the application's main thread before starting workers.
 * Repeated calls are safe. Gwyddion type setup is protected by GLib once. */
AFM_GWY_API int afm_gwyddion_init(void);

/* Arrays are contiguous row-major float64; include_mask is NULL or binary
 * 1=selected. All data must be finite: the caller owns invalid-pixel policy.
 * Physical xreal/yreal and Z data use consistent SI units for matching/facets.
 * Inputs are never modified. Output buffers are caller-owned. No output array
 * is committed on failure. axis: 0=rows,1=columns. offsets has rows/cols items.
 */
AFM_GWY_API int afm_gwyddion_align(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, int axis, int method, int degree,
    double trim_fraction, double *output, double *offsets);

/* coeffs3 is the SUBTRACTED plane (c,bx,by) in zero-based pixel indices;
 * c=-0.5*(bx*cols+by*rows), as in Gwyddion's Plane Level module.
 */
AFM_GWY_API int afm_gwyddion_plane(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, double *output, double *coeffs3);

/* Zero-reference mode: 0=mean, 1=minimum, 2=maximum. offset is subtracted. */
AFM_GWY_API int afm_gwyddion_zero(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, int mode, double *output, double *offset);

/* mode:0 independent degrees,1 limited total degree. Degree bounds 0..11.
 * Caller provides coeffs[144], powers[288], nterms. Terms are ascending x
 * power then y power, on [-1,1] at first/last pixel centres, monomial basis.
 * The caller must reject rank-deficient reference geometry before calling;
 * count/dimension checks also run here. No Python polynomial output is used.
 */
AFM_GWY_API int afm_gwyddion_polynomial(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, int mode, int degree_x, int degree_y, int degree,
    double *output, double *coeffs144, int *powers288, int *nterms);

/* stats9: mean,Sa,Sq,skewness,excess_kurtosis,upper_median,min,max,count. */
AFM_GWY_API int afm_gwyddion_stats(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, double *stats9);

/* Endpoints are physical field coordinates. interpolation:0 nearest,1 linear.
 * samples 2..65536, thickness 1..128. Distance/value buffers hold at least
 * samples items. Masked-out samples may be omitted by the upstream function;
 * nwritten is the returned number and distances preserve their positions.
 */
AFM_GWY_API int afm_gwyddion_profile(
    const double *data, const double *include_mask, int rows, int cols,
    double xreal, double yreal, double x0, double y0, double x1, double y1,
    int samples, int thickness, int interpolation,
    double *distances, double *values, int *nwritten);

#ifdef __cplusplus
}
#endif
#endif
