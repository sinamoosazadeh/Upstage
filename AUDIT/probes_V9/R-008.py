"""R-008: hamilton_filter_step normalizes with den = sum(num) + EPS; when
the Gaussian emission underflows to 0 (perfectly possible: exp(log_e) with
log_e < -745), num = 0 and xi_filt collapses to the zero vector — no
longer a probability simplex — and the filter state is absorbed at zero
forever."""
import math
import numpy as np
from apex.engines.e11_regime.engine import (hamilton_filter_step,
                                            gaussian_log_emission, K)

T = np.full((K, K), 1.0 / K)
xi = np.full(K, 1.0 / K)

# realistic underflow: turbulent bar far from mu -> log emission << -745
mu = np.full(8, 0.5)
Sigma = 0.055 * np.eye(8)
x_far = np.full(8, 250.0)                    # |x-mu| ~ 250 per dim
log_e = gaussian_log_emission(x_far, mu, Sigma)
eta_scalar = math.exp(log_e) if log_e > -745 else 0.0
print("log emission = %.1f -> eta = %r (underflow)" % (log_e, eta_scalar))
eta = np.full(K, eta_scalar)
xi_pred, xi_filt = hamilton_filter_step(xi, T, eta)
print("xi_pred sum = %.6f | xi_filt = %s sum = %.6f" % (
    xi_pred.sum(), xi_filt, xi_filt.sum()))
assert abs(xi_filt.sum()) < 1e-9, "filter state collapsed to zeros"

# absorbed forever: next step with HEALTHY eta cannot recover
eta_ok = np.full(K, 0.5)
_, xi_next = hamilton_filter_step(xi_filt, T, eta_ok)
print("next step with healthy eta: xi = %s sum = %.6f" % (
    xi_next, xi_next.sum()))
assert abs(xi_next.sum()) < 1e-9
print("R-008 CONFIRMED: EPS-padded normalization silently leaves the "
      "simplex on emission underflow; zero state is absorbing")
