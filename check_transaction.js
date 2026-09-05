async function run() {
  const res = await fetch("https://sandbox-api.paddle.com/transactions", {
    method: "POST",
    headers: {
      "Authorization": "Bearer PADDLE_API_KEY_REDACTED",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      items: [
        {
          price_id: "pri_01m1psq971t3sy5h2xq0venhsg",
          quantity: 1
        }
      ]
    })
  });
  const data = await res.json();
  console.log(JSON.stringify(data, null, 2));
}
run();
