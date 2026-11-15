/* SPDX-License-Identifier: GPL-2.0-or-later
 * AFM Workbench's narrow ABI around the real Gwyddion scientific libraries.
 * The generated include contains unchanged GPL Gwyddion module helpers, with
 * its upstream copyright notice. No Gwyddion object or algorithm is emulated.
 */
#include "afm_gwyddion.h"

#include <float.h>
#include <math.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include <libgwyddion/gwyddion.h>
#include <libgwyddion/gwyomp.h>
#include <libprocess/gwyprocess.h>

static void zero_level_row_shifts(GwyDataLine *shifts);
#include "gwyddion_linematch.inc"

const char *afm_gwyddion_version(void)
{
    return gwy_version_string();
}

int afm_gwyddion_abi_version(void)
{
    return 1;
}

int afm_gwyddion_init(void)
{
    static gsize initialized = 0;
    if (g_once_init_enter(&initialized)) {
        gwy_process_type_init();
        gwy_threads_set_enabled(FALSE);
        g_once_init_leave(&initialized, 1);
    }
    return AFM_GWY_OK;
}

static int validate_field(const double *data, const double *mask,
                          int rows, int cols, double xreal, double yreal,
                          size_t *count, size_t *selected)
{
    size_t n, used = 0;
    if (!data || rows <= 0 || cols <= 0 || !isfinite(xreal) || !isfinite(yreal)
        || xreal <= 0.0 || yreal <= 0.0)
        return AFM_GWY_ARGUMENT;
    n = (size_t)rows * (size_t)cols;
    if (n > G_MAXINT || n > SIZE_MAX/sizeof(double))
        return AFM_GWY_ARGUMENT;
    for (size_t i = 0; i < n; i++) {
        if (!isfinite(data[i]))
            return AFM_GWY_NONFINITE;
        if (mask && mask[i] != 0.0 && mask[i] != 1.0)
            return AFM_GWY_ARGUMENT;
        used += !mask || mask[i] == 1.0;
    }
    *count = n;
    *selected = used;
    return AFM_GWY_OK;
}

static GwyDataField *new_field(const double *data, int rows, int cols,
                              double xreal, double yreal)
{
    GwyDataField *field = gwy_data_field_new(cols, rows, xreal, yreal, FALSE);
    if (field)
        memcpy(gwy_data_field_get_data(field), data,
               (size_t)rows * (size_t)cols * sizeof(double));
    return field;
}

static GwyDataField *transpose_field(GwyDataField *field)
{
    GwyDataField *transposed = gwy_data_field_new_alike(field, FALSE);
    gwy_data_field_flip_xy(field, transposed, FALSE);
    g_object_unref(field);
    return transposed;
}

static int finite_values(const double *data, size_t count)
{
    for (size_t i = 0; i < count; i++) {
        if (!isfinite(data[i]))
            return FALSE;
    }
    return TRUE;
}

static size_t row_selected(const double *excluded, int width)
{
    size_t n = 0;
    for (int j = 0; j < width; j++)
        n += !excluded || excluded[j] == 0.0;
    return n;
}

/* Run the upstream facet estimate and subtraction helpers, adding only a
 * zero-variance guard before each iteration. The module itself computes 0/0
 * on an exactly flat row. Nonfinite nondegenerate estimates fail atomically.
 */
static int safe_facet_tilt(GwyDataField *field, GwyDataField *mask)
{
    int width = gwy_data_field_get_xres(field);
    int height = gwy_data_field_get_yres(field);
    guint minimum = GWY_ROUND(log(width) + 1.0);
    double dx = gwy_data_field_get_dx(field);
    double *data = gwy_data_field_get_data(field);
    const double *excluded = mask ? gwy_data_field_get_data_const(mask) : NULL;
    GwyMaskingType masking = mask ? GWY_MASK_EXCLUDE : GWY_MASK_IGNORE;

    for (int i = 0; i < height; i++) {
        double *row = data + (size_t)i*width;
        const double *mrow = excluded ? excluded + (size_t)i*width : NULL;
        for (int iteration = 0; iteration < 30; iteration++) {
            int nonflat = FALSE;
            for (int j = 0; j < width-1; j++) {
                if ((!mrow || (mrow[j] == 0.0 && mrow[j+1] == 0.0))
                    && row[j] != row[j+1]) {
                    nonflat = TRUE;
                    break;
                }
            }
            if (!nonflat)
                break;
            double tilt = row_fit_facet_tilt(row, mrow, masking, width, dx, minimum);
            if (!isfinite(tilt))
                return AFM_GWY_NONFINITE;
            untilt_row(row, width, tilt);
            if (fabs(tilt/dx) < 1e-6)
                break;
        }
    }
    gwy_data_field_invalidate(field);
    return AFM_GWY_OK;
}

int afm_gwyddion_align(const double *data, const double *include_mask,
                       int rows, int cols, double xreal, double yreal,
                       int axis, int method, int degree, double trim_fraction,
                       double *output, double *offsets)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    GwyDataField *field = NULL, *mask = NULL, *original = NULL;
    GwyDataLine *shifts = NULL;
    if (status)
        return status;
    if (!output || !offsets || (axis != 0 && axis != 1) || method < 0 || method > 8
        || degree < 0 || degree > 5 || !isfinite(trim_fraction)
        || trim_fraction < 0.0 || trim_fraction > 0.5)
        return AFM_GWY_ARGUMENT;
    if (!selected)
        return AFM_GWY_REFERENCE;

    field = new_field(data, rows, cols, xreal, yreal);
    if (include_mask)
        mask = new_field(include_mask, rows, cols, xreal, yreal);
    if (axis) {
        field = transpose_field(field);
        if (mask)
            mask = transpose_field(mask);
    }
    int width = gwy_data_field_get_xres(field);
    int height = gwy_data_field_get_yres(field);
    if (mask) {
        /* Exclusion of the inverse is equivalent for binary masks, and avoids
         * Gwyddion 2.71's trimmed-difference INCLUDE test requiring >1. */
        double *m = gwy_data_field_get_data(mask);
        for (size_t i = 0; i < n; i++)
            m[i] = 1.0 - m[i];
    }
    GwyMaskingType masking = mask ? GWY_MASK_EXCLUDE : GWY_MASK_IGNORE;
    shifts = gwy_data_line_new(height, gwy_data_field_get_yreal(field), TRUE);

    if (method == AFM_GWY_MEAN || method == AFM_GWY_MEDIAN
        || method == AFM_GWY_TRIMMED_MEAN || (method == AFM_GWY_POLYNOMIAL && degree == 0)) {
        double trim = method == AFM_GWY_MEDIAN ? 0.5
                      : method == AFM_GWY_TRIMMED_MEAN ? trim_fraction : 0.0;
        g_object_unref(shifts);
        shifts = gwy_data_field_find_row_shifts_trimmed_mean(field, mask, masking, trim, 0);
        if (!shifts) {
            status = AFM_GWY_FAILURE;
            goto cleanup;
        }
        gwy_data_field_subtract_row_shifts(field, shifts);
    }
    else if (method == AFM_GWY_MEDIAN_DIFFERENCE || method == AFM_GWY_TRIMMED_DIFFERENCE) {
        if (height > 1) {
            double trim = method == AFM_GWY_MEDIAN_DIFFERENCE ? 0.5 : trim_fraction;
            g_object_unref(shifts);
            shifts = gwy_data_field_find_row_shifts_trimmed_diff(field, mask, masking, trim, 0);
            if (!shifts) {
                status = AFM_GWY_FAILURE;
                goto cleanup;
            }
            gwy_data_field_subtract_row_shifts(field, shifts);
        }
    }
    else if (method == AFM_GWY_MODUS)
        linematch_do_modus(field, mask, shifts, masking);
    else if (method == AFM_GWY_MATCHING)
        linematch_do_match(field, mask, shifts, masking);
    else if (method == AFM_GWY_FACET_TILT) {
        status = safe_facet_tilt(field, mask);
        if (status)
            goto cleanup;
    }
    else {
        original = gwy_data_field_duplicate(field);
        gwy_data_field_row_level_poly(field, mask, masking, degree, shifts);
        /* An insufficient row must not acquire the image mean merely because
         * upstream represents a failed row fit with all-zero coefficients. */
        double *result = gwy_data_field_get_data(field);
        double *shift = gwy_data_line_get_data(shifts);
        const double *before = gwy_data_field_get_data_const(original);
        const double *excluded = mask ? gwy_data_field_get_data_const(mask) : NULL;
        for (int i = 0; i < height; i++) {
            if (row_selected(excluded ? excluded + (size_t)i*width : NULL, width) <= (size_t)degree) {
                memcpy(result + (size_t)i*width, before + (size_t)i*width, width*sizeof(double));
                shift[i] = 0.0;
            }
        }
        gwy_data_field_invalidate(field);
    }
    if (!finite_values(gwy_data_field_get_data_const(field), n)
        || !finite_values(gwy_data_line_get_data_const(shifts), height)) {
        status = AFM_GWY_NONFINITE;
        goto cleanup;
    }
    if (axis)
        field = transpose_field(field);
    memcpy(output, gwy_data_field_get_data_const(field), n*sizeof(double));
    memcpy(offsets, gwy_data_line_get_data_const(shifts), height*sizeof(double));

cleanup:
    if (shifts) g_object_unref(shifts);
    if (original) g_object_unref(original);
    if (mask) g_object_unref(mask);
    if (field) g_object_unref(field);
    return status;
}

static int plane_reference_spans_area(const double *mask, int rows, int cols)
{
    long double n = 0, sx = 0, sy = 0, xx = 0, yy = 0, xy = 0;
    for (int i = 0; i < rows; i++) {
        for (int j = 0; j < cols; j++) {
            if (mask && mask[(size_t)i*cols+j] == 0.0)
                continue;
            long double x = (long double)j/cols, y = (long double)i/rows;
            n++; sx += x; sy += y; xx += x*x; yy += y*y; xy += x*y;
        }
    }
    if (n < 3)
        return FALSE;
    xx -= sx*sx/n;
    yy -= sy*sy/n;
    xy -= sx*sy/n;
    return xx > 0 && yy > 0 && xx*yy-xy*xy > 32*LDBL_EPSILON*xx*yy;
}

int afm_gwyddion_plane(const double *data, const double *include_mask,
                       int rows, int cols, double xreal, double yreal,
                       double *output, double *coeffs3)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    if (status)
        return status;
    if (!output || !coeffs3)
        return AFM_GWY_ARGUMENT;
    if (!plane_reference_spans_area(include_mask, rows, cols))
        return AFM_GWY_REFERENCE;
    GwyDataField *field = new_field(data, rows, cols, xreal, yreal);
    GwyDataField *mask = include_mask ? new_field(include_mask, rows, cols, xreal, yreal) : NULL;
    double c, bx, by;
    if (mask)
        gwy_data_field_area_fit_plane(field, mask, 0, 0, cols, rows, &c, &bx, &by);
    else
        gwy_data_field_fit_plane(field, &c, &bx, &by);
    c = -0.5*(bx*cols + by*rows);
    gwy_data_field_plane_level(field, c, bx, by);
    if (!finite_values(gwy_data_field_get_data_const(field), n)
        || !isfinite(c) || !isfinite(bx) || !isfinite(by))
        status = AFM_GWY_NONFINITE;
    else {
        memcpy(output, gwy_data_field_get_data_const(field), n*sizeof(double));
        coeffs3[0] = c; coeffs3[1] = bx; coeffs3[2] = by;
    }
    if (mask) g_object_unref(mask);
    g_object_unref(field);
    return status;
}

int afm_gwyddion_zero(const double *data, const double *include_mask,
                      int rows, int cols, double xreal, double yreal,
                      int mode, double *output, double *offset)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    if (status)
        return status;
    if (!output || !offset || mode < 0 || mode > 2)
        return AFM_GWY_ARGUMENT;
    if (!selected)
        return AFM_GWY_REFERENCE;
    GwyDataField *field = new_field(data, rows, cols, xreal, yreal);
    GwyDataField *mask = include_mask ? new_field(include_mask, rows, cols, xreal, yreal) : NULL;
    GwyMaskingType masking = mask ? GWY_MASK_INCLUDE : GWY_MASK_IGNORE;
    double reference;
    if (mode == 0)
        reference = gwy_data_field_area_get_avg_mask(field, mask, masking, 0, 0, cols, rows);
    else
        gwy_data_field_area_get_min_max_mask(field, mask, masking, 0, 0, cols, rows,
                                            mode == 1 ? &reference : NULL,
                                            mode == 2 ? &reference : NULL);
    gwy_data_field_add(field, -reference);
    if (!isfinite(reference) || !finite_values(gwy_data_field_get_data_const(field), n))
        status = AFM_GWY_NONFINITE;
    else {
        memcpy(output, gwy_data_field_get_data_const(field), n*sizeof(double));
        *offset = reference;
    }
    if (mask) g_object_unref(mask);
    g_object_unref(field);
    return status;
}

/* fit_poly clears coefficients when its Cholesky factorization fails, but
 * does not expose a failure flag. A genuinely zero least-squares fit must be
 * orthogonal to every requested basis term. Check this only on the all-zero
 * return path; the library still supplies every successful fit coefficient.
 */
static int zero_polynomial_satisfies_normal_equations(
    const double *data, const double *mask, int rows, int cols,
    int terms, const int *powers)
{
    long double moments[144] = {0}, absolute_sum = 0;
    for (int i = 0; i < rows; i++) {
        long double y = 2.0L*i/(rows-1) - 1.0L;
        long double yp[12];
        yp[0] = 1;
        for (int k = 1; k < 12; k++)
            yp[k] = yp[k-1]*y;
        for (int j = 0; j < cols; j++) {
            size_t index = (size_t)i*cols+j;
            if (mask && mask[index] == 0.0)
                continue;
            long double x = 2.0L*j/(cols-1) - 1.0L;
            long double z = data[index], xp[12];
            xp[0] = 1;
            for (int k = 1; k < 12; k++)
                xp[k] = xp[k-1]*x;
            absolute_sum += fabsl(z);
            for (int k = 0; k < terms; k++)
                moments[k] += z*xp[powers[2*k]]*yp[powers[2*k+1]];
        }
    }
    long double tolerance = 128.0L*DBL_EPSILON*absolute_sum;
    for (int k = 0; k < terms; k++) {
        if (fabsl(moments[k]) > tolerance)
            return FALSE;
    }
    return TRUE;
}

int afm_gwyddion_polynomial(const double *data, const double *include_mask,
                            int rows, int cols, double xreal, double yreal,
                            int mode, int degree_x, int degree_y, int degree,
                            double *output, double *coeffs144, int *powers288, int *nterms)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    if (status)
        return status;
    if (!output || !coeffs144 || !powers288 || !nterms || (mode != 0 && mode != 1)
        || degree_x < 0 || degree_x > 11 || degree_y < 0 || degree_y > 11 || degree < 0 || degree > 11)
        return AFM_GWY_ARGUMENT;
    int dx = mode ? degree : degree_x, dy = mode ? degree : degree_y;
    if (rows < 2 || cols < 2 || dx >= cols || dy >= rows)
        return AFM_GWY_REFERENCE;
    int terms = 0, powers[288];
    for (int i = 0; i <= dx; i++) {
        for (int j = 0; j <= dy; j++) {
            if (mode && i+j > degree)
                continue;
            powers[2*terms] = i;
            powers[2*terms+1] = j;
            terms++;
        }
    }
    if (selected < (size_t)terms)
        return AFM_GWY_REFERENCE;
    GwyDataField *field = new_field(data, rows, cols, xreal, yreal);
    GwyDataField *mask = include_mask ? new_field(include_mask, rows, cols, xreal, yreal) : NULL;
    double *coeffs = gwy_data_field_fit_poly(field, mask, terms, powers, FALSE, NULL);
    if (!coeffs)
        status = AFM_GWY_FAILURE;
    else {
        int all_zero = TRUE;
        for (int k = 0; k < terms; k++)
            all_zero = all_zero && coeffs[k] == 0.0;
        if (all_zero && !zero_polynomial_satisfies_normal_equations(
                                data, include_mask, rows, cols, terms, powers))
            status = AFM_GWY_FAILURE;
        if (!status) {
            gwy_data_field_subtract_poly(field, terms, powers, coeffs);
            if (!finite_values(gwy_data_field_get_data_const(field), n) || !finite_values(coeffs, terms))
                status = AFM_GWY_NONFINITE;
            else {
                memcpy(output, gwy_data_field_get_data_const(field), n*sizeof(double));
                memcpy(coeffs144, coeffs, terms*sizeof(double));
                memcpy(powers288, powers, 2*terms*sizeof(int));
                *nterms = terms;
            }
        }
        g_free(coeffs);
    }
    if (mask) g_object_unref(mask);
    g_object_unref(field);
    return status;
}

int afm_gwyddion_stats(const double *data, const double *include_mask,
                       int rows, int cols, double xreal, double yreal,
                       double *stats9)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    if (status)
        return status;
    if (!stats9)
        return AFM_GWY_ARGUMENT;
    if (!selected)
        return AFM_GWY_REFERENCE;
    GwyDataField *field = new_field(data, rows, cols, xreal, yreal);
    GwyDataField *mask = include_mask ? new_field(include_mask, rows, cols, xreal, yreal) : NULL;
    GwyMaskingType masking = mask ? GWY_MASK_INCLUDE : GWY_MASK_IGNORE;
    double stats[9];
    gwy_data_field_area_get_stats_mask(field, mask, masking, 0, 0, cols, rows,
                                      stats, stats+1, stats+2, stats+3, stats+4);
    stats[5] = gwy_data_field_area_get_median_mask(field, mask, masking, 0, 0, cols, rows);
    gwy_data_field_area_get_min_max_mask(field, mask, masking, 0, 0, cols, rows, stats+6, stats+7);
    stats[8] = (double)selected;
    if (!finite_values(stats, 9))
        status = AFM_GWY_NONFINITE;
    else
        memcpy(stats9, stats, sizeof(stats));
    if (mask) g_object_unref(mask);
    g_object_unref(field);
    return status;
}

int afm_gwyddion_profile(const double *data, const double *include_mask,
                         int rows, int cols, double xreal, double yreal,
                         double x0, double y0, double x1, double y1,
                         int samples, int thickness, int interpolation,
                         double *distances, double *values, int *nwritten)
{
    size_t n, selected;
    int status = validate_field(data, include_mask, rows, cols, xreal, yreal, &n, &selected);
    if (status)
        return status;
    if (!distances || !values || !nwritten || samples < 2 || samples > 65536
        || thickness < 1 || thickness > 128 || (interpolation != 0 && interpolation != 1)
        || !isfinite(x0) || !isfinite(y0) || !isfinite(x1) || !isfinite(y1)
        || x0 < 0 || y0 < 0 || x1 < 0 || y1 < 0 || x0 > xreal || x1 > xreal
        || y0 > yreal || y1 > yreal || (x0 == x1 && y0 == y1))
        return AFM_GWY_ARGUMENT;
    if (!selected) {
        *nwritten = 0;
        return AFM_GWY_OK;
    }
    GwyDataField *field = new_field(data, rows, cols, xreal, yreal);
    GwyDataField *mask = include_mask ? new_field(include_mask, rows, cols, xreal, yreal) : NULL;
    int count = 0;
    GwyXY *profile = gwy_data_field_get_profile_mask(field, &count, mask,
                            mask ? GWY_MASK_INCLUDE : GWY_MASK_IGNORE,
                            x0, y0, x1, y1, samples, thickness,
                            interpolation ? GWY_INTERPOLATION_LINEAR : GWY_INTERPOLATION_ROUND);
    if (count < 0 || count > samples || (count && !profile))
        status = AFM_GWY_FAILURE;
    else {
        for (int i = 0; i < count; i++) {
            if (!isfinite(profile[i].x) || !isfinite(profile[i].y)) {
                status = AFM_GWY_NONFINITE;
                break;
            }
        }
        if (!status) {
            for (int i = 0; i < count; i++) {
                distances[i] = profile[i].x;
                values[i] = profile[i].y;
            }
            *nwritten = count;
        }
    }
    g_free(profile);
    if (mask) g_object_unref(mask);
    g_object_unref(field);
    return status;
}
