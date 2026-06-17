// Smoke tests for member service
const http = require("http");

const BASE = "http://localhost:8082";

function jsonGet(path) {
  return new Promise((resolve, reject) => {
    http.get(`${BASE}${path}`, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch (e) {
          reject(new Error(`Parse error: ${e.message}, raw: ${data.slice(0, 200)}`));
        }
      });
    }).on("error", reject);
  });
}

async function runTests() {
  let passed = 0;
  let failed = 0;

  // Test 1: Health check
  try {
    const r = await jsonGet("/healthz");
    if (r.status === 200 && r.body.status === "ok" && r.body.service === "member") {
      console.log("PASS  test_healthz");
      passed++;
    } else {
      console.log("FAIL  test_healthz", r.body);
      failed++;
    }
  } catch (e) {
    console.log("FAIL  test_healthz", e.message);
    failed++;
  }

  // Test 2: Get overview
  try {
    const r = await jsonGet("/api/members/me/overview");
    if (r.status === 200 && r.body.code === 0 && r.body.data.profile) {
      console.log("PASS  test_get_overview");
      passed++;
    } else {
      console.log("FAIL  test_get_overview", r.body);
      failed++;
    }
  } catch (e) {
    console.log("FAIL  test_get_overview", e.message);
    failed++;
  }

  // Test 3: List levels
  try {
    const r = await jsonGet("/api/members/levels");
    if (r.status === 200 && r.body.data.list.length === 3) {
      console.log("PASS  test_list_levels");
      passed++;
    } else {
      console.log("FAIL  test_list_levels", r.body);
      failed++;
    }
  } catch (e) {
    console.log("FAIL  test_list_levels", e.message);
    failed++;
  }

  // Test 4: Get coupons
  try {
    const r = await jsonGet("/api/members/me/coupons");
    if (r.status === 200 && r.body.code === 0) {
      console.log("PASS  test_get_coupons");
      passed++;
    } else {
      console.log("FAIL  test_get_coupons", r.body);
      failed++;
    }
  } catch (e) {
    console.log("FAIL  test_get_coupons", e.message);
    failed++;
  }

  // Test 5: Get points
  try {
    const r = await jsonGet("/api/members/me/points?page=1&size=5");
    if (r.status === 200 && r.body.data.total >= 0) {
      console.log("PASS  test_get_points");
      passed++;
    } else {
      console.log("FAIL  test_get_points", r.body);
      failed++;
    }
  } catch (e) {
    console.log("FAIL  test_get_points", e.message);
    failed++;
  }

  console.log(`\nResults: ${passed} passed, ${failed} failed`);
  process.exit(failed > 0 ? 1 : 0);
}

runTests();
