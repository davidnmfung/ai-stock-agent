import { clerkMiddleware } from "@clerk/nextjs/server";

export default clerkMiddleware();

export const config = {
  matcher: [
    // 略過 Next.js 內部檔案與靜態資源
    '/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)',
    // 允許 API 路由
    '/(api|trpc)(.*)',
    // 必須包含此行以支援 Clerk App Proxy 路由
    '/__clerk/:path*',
  ],
};