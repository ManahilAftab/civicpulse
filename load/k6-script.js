// Load test for the HPA demo:  k6 run load/k6-script.js
// Ramps offered load up and down so `kubectl get hpa -w` shows scale-out and scale-in.
import http from "k6/http";
import { check, sleep } from "k6";

const BASE = __ENV.BASE_URL || "http://civicpulse.localhost:8080";

export const options = {
  stages: [
    { duration: "1m", target: 20 },
    { duration: "3m", target: 80 },
    { duration: "1m", target: 0 },
  ],
};

export default function () {
  const res = http.get(`${BASE}/api/complaints?page_size=50`);
  check(res, { "status 200": (r) => r.status === 200 });
  sleep(0.1);
}
