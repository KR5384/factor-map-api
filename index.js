export default {
  // すべてのHTTPリクエストはこの fetch メソッドに入ってきます
  async fetch(request, env, ctx) {
    // 1. リクエストのURLやメソッド（GET, POSTなど）を取得
    const url = new URL(request.url);
    const method = request.method;

    // 2. アクセスされたURL（ルーティング）によって処理を分岐
    
    // 例: /api/hello にアクセスされた場合
    if (url.pathname === "/api/hello" && method === "GET") {
      const data = {
        message: "バックエンドからの挨拶です！通信成功です。",
        status: "success"
      };
      
      // フロントエンド（画面）にJSON形式でデータを返す
      return new Response(JSON.stringify(data), {
        headers: {
          "Content-Type": "application/json",
          // CORS設定（フロントエンドからのアクセスを許可するため）
          "Access-Control-Allow-Origin": "*" 
        },
      });
    }

    // 例: /api/users にアクセスされた場合 (今後D1データベース等と繋ぐ場所)
    if (url.pathname === "/api/users" && method === "GET") {
      // 📝 WebのGUIで紐付けたD1データベースには、ここから env.DB のようにアクセスできます
      // const { results } = await env.DB.prepare("SELECT * FROM users").all();
      
      const mockData = [
        { id: 1, name: "こみやん" },
        { id: 2, name: "たいちゃん" },
        { id: 3, name: "森" }
      ];
      
      return new Response(JSON.stringify(mockData), {
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*"
        },
      });
    }

    // 3. 該当するURLがない場合は 404 Not Found を返す
    return new Response(JSON.stringify({ error: "Not Found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" }
    });
  },
};