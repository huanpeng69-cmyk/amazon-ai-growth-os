// Vite 开发服务器配置（仅用于本地开发热更新；生产构建走 build.mjs）。
//
// 源码 index.html 以 /static/assets/... 引用资源（与后端 StaticFiles 挂载一致），
// 但本地源文件实际在 frontend/assets/ 下。此处用一个小插件把 /static/* 重写到
// /assets/*，使 `npm run dev` 能正确服务未构建的源码，同时获得 HMR。

import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

export default {
  root: __dirname,
  server: {
    port: 5173,
    // 后端 API 在 8002（或经代理），开发时前端走同源代理避免 CORS
    proxy: {
      "/api": "http://127.0.0.1:8002",
    },
  },
  plugins: [
    {
      name: "rewrite-static-to-assets",
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url && req.url.startsWith("/static/")) {
            req.url = req.url.replace("/static/", "/assets/");
          }
          next();
        });
      },
    },
  ],
};
