import type { Metadata } from "next";
import "./globals.css";
export const metadata:Metadata={title:"ContractGuard — Hiểu rõ trước khi ký",description:"Trợ lý AI giúp sinh viên kiểm tra tính toàn vẹn và phát hiện rủi ro trong hợp đồng.",icons:{icon:"/favicon.svg",shortcut:"/favicon.svg"}};
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="vi"><body>{children}</body></html>}
