import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
 plugins:[react()],
 server:{host:"127.0.0.1",port:5174,strictPort:true,
 proxy:Object.fromEntries(["/health","/ws","/sessions","/company"].map(p=>[p,{target:"http://127.0.0.1:8001",ws:true}]))}
});
