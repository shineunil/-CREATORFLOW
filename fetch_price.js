async function run() {
  const res = await fetch("https://sandbox-api.paddle.com/prices?product_id=pro_01m1psg2rnwgtvsjevgkyjq9j9", {
    headers: {
      "Authorization": "Bearer PADDLE_API_KEY_REDACTED"
    }
  });
  const data = await res.json();
  console.log(JSON.stringify(data, null, 2));
}
run();
