async function run() {
  const res = await fetch("https://sandbox-api.paddle.com/prices/pri_01m1psq971t3sy5h2xq0venhsg", {
    headers: {
      "Authorization": "Bearer PADDLE_API_KEY_REDACTED"
    }
  });
  console.log(res.status);
  const data = await res.json();
  console.log(JSON.stringify(data, null, 2));
}
run();
