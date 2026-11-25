import { AntdRegistry } from '@ant-design/nextjs-registry';
import 'antd/dist/reset.css';
import './globals.css';
export const metadata = { title: 'Хүүхдийн эрүүл мэндийн RAG туслах', description: 'WHO эх сурвалжтай мэдээллийн туслах' };
export default function Layout({ children }: { children: React.ReactNode }) {
  return <html lang="mn"><body><AntdRegistry>{children}</AntdRegistry></body></html>;
}
