"use client";
import { Alert, Button, Card, Divider, Form, Input, Segmented, Typography } from "antd";
import Script from "next/script";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";

type GoogleConfig = { enabled: boolean; client_id?: string; nonce?: string };
declare global {
  interface Window {
    google?: { accounts: { id: {
      initialize: (options: { client_id: string; nonce: string; auto_select: boolean;
        callback: (response: { credential: string }) => void }) => void;
      renderButton: (element: HTMLElement, options: Record<string, string | number>) => void;
    } } };
  }
}
export default function Login() {
  const router = useRouter();
  const [register, setRegister] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [googleConfig, setGoogleConfig] = useState<GoogleConfig>();
  const [googleReady, setGoogleReady] = useState(false);
  const googleButton = useRef<HTMLDivElement>(null);
  const pending = useRef(false);
  useEffect(() => {
    let cancelled = false;
    api<GoogleConfig>("/auth/google/config").then(value => {
      if (!cancelled) setGoogleConfig(value);
    }).catch(() => { if (!cancelled) setGoogleConfig({ enabled: false }); });
    return () => { cancelled = true; };
  }, []);
  useEffect(() => {
    const google = window.google;
    if (!googleReady || !google || !googleButton.current || !googleConfig?.client_id || !googleConfig.nonce) return;
    google.accounts.id.initialize({
      client_id: googleConfig.client_id, nonce: googleConfig.nonce, auto_select: false,
      callback: async ({ credential }) => {
        if (pending.current) return;
        pending.current = true; setLoading(true); setError("");
        try {
          await api("/auth/google/login", { credential });
          router.replace("/chat");
        } catch (e) {
          setError(e instanceof Error ? e.message : "Google нэвтрэлт амжилтгүй.");
        } finally { pending.current = false; setLoading(false); }
      },
    });
    googleButton.current.replaceChildren();
    google.accounts.id.renderButton(googleButton.current, { theme: "outline", size: "large", width: 300 });
  }, [googleReady, googleConfig, router]);
  async function submit(values: { username: string; password: string }) {
    if (pending.current) return;
    pending.current = true; setLoading(true); setError("");
    try {
      await api(register ? "/auth/register" : "/auth/login", {
        username: values.username, password: values.password,
      });
      router.replace("/chat");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Хүсэлт амжилтгүй.");
    } finally { pending.current = false; setLoading(false); }
  }
  return (
    <main className="login">
      <Card className="login-card">
        <Typography.Title level={3}>{register ? "Бүртгүүлэх" : "Нэвтрэх"}</Typography.Title>
        <Typography.Paragraph type="secondary">Хүүхдийн эрүүл мэндийн мэдээллийн туслах</Typography.Paragraph>
        <Segmented block disabled={loading} value={register ? "register" : "login"}
          options={[{ label: "Нэвтрэх", value: "login" }, { label: "Бүртгүүлэх", value: "register" }]}
          onChange={value => { setRegister(value === "register"); setError(""); }} style={{ marginBottom: 20 }} />
        {error && <Alert title={error} type="error" showIcon style={{ marginBottom: 20 }} />}
        <Form key={String(register)} layout="vertical" onFinish={submit} requiredMark={false} disabled={loading}>
          <Form.Item name="username" label="Хэрэглэгчийн нэр" rules={[
            { required: true, message: "Хэрэглэгчийн нэрээ оруулна уу." },
            ...(register ? [{ pattern: /^[a-z0-9][a-z0-9_.-]{2,49}$/, message: "3–50 жижиг латин үсэг, тоо, _, . эсвэл - ашиглана уу." }] : []),
          ]}>
            <Input autoComplete="username" autoFocus maxLength={register ? 50 : 100} />
          </Form.Item>
          <Form.Item name="password" label="Нууц үг" rules={[
            { required: true, message: "Нууц үгээ оруулна уу." },
            ...(register ? [{ min: 12, message: "Нууц үг 12-оос доошгүй тэмдэгт байна." }] : []),
          ]}>
            <Input.Password autoComplete={register ? "new-password" : "current-password"} maxLength={256} />
          </Form.Item>
          {register && <Form.Item name="confirm" label="Нууц үг давтах" dependencies={["password"]}
            rules={[{ required: true, message: "Нууц үгээ давтан оруулна уу." }, ({ getFieldValue }) => ({
              validator(_, value) { return !value || getFieldValue("password") === value
                ? Promise.resolve() : Promise.reject(new Error("Нууц үг таарахгүй байна.")); },
            })]}><Input.Password autoComplete="new-password" maxLength={256} /></Form.Item>}
          <Button type="primary" htmlType="submit" block loading={loading}>{register ? "Бүртгүүлээд нэвтрэх" : "Нэвтрэх"}</Button>
        </Form>
        {googleConfig?.enabled && <>
          <Divider>эсвэл</Divider>
          <Script src="https://accounts.google.com/gsi/client" onReady={() => setGoogleReady(true)}
            onError={() => setError("Google товч ачаалагдсангүй. Хуудсыг шинэчилнэ үү.")} />
          <div ref={googleButton} style={{ display: "flex", justifyContent: "center", pointerEvents: loading ? "none" : "auto" }} />
          <Typography.Paragraph type="secondary" style={{ marginTop: 12 }}>
            Google-ээр анх нэвтрэхэд шинэ бүртгэл үүснэ.
          </Typography.Paragraph>
        </>}
      </Card>
    </main>
  );
}
