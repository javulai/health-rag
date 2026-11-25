"use client";
import {
  Alert,
  Button,
  Drawer,
  Input,
  Spin,
  Typography,
} from "antd";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "@/lib/api";
type Source = {
  title: string;
  source_url: string;
  locator: string;
  citation_id: number;
};
type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};
export default function Chat() {
  const router = useRouter();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [user, setUser] = useState("");
  const [conversations, setConversations] = useState<{id: string; title: string}[]>([]);
  const [conversationId, setConversationId] = useState<string | undefined>();
  const [loadingHistory, setLoadingHistory] = useState(false);
  const loadVersion = useRef(0);
  const retry = useRef<{id: string; text: string; conversation?: string} | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [leaving, setLeaving] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const sending = useRef(false);
  useEffect(() => {
    api<{ username: string }>("/auth/me")
      .then(async (x) => { setUser(x.username); await loadConversations(); })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) router.replace("/login");
        else
          setError("Сервертэй холбогдож чадсангүй. Хуудсыг дахин ачаална уу.");
      });
  }, [router]);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);
  async function loadConversations() {
    let all: {id: string; title: string}[] = [];
    for (let offset=0; ; offset+=50) {
      const batch=await api<{id: string; title: string}[]>(`/conversations?offset=${offset}`);
      all=all.concat(batch); if(batch.length<50) break;
    }
    setConversations(all);
  }
  async function openConversation(id: string) {
    const version=++loadVersion.current; setLoadingHistory(true); setError("");
    try {
      let all: Message[]=[];
      for(let offset=0; ; offset+=100) {
        const page=await api<{messages: Message[]}>(`/conversations/${id}?offset=${offset}`);
        all=all.concat(page.messages); if(page.messages.length<100) break;
      }
      if(version===loadVersion.current) {setConversationId(id);setMessages(all);retry.current=null;setQuestion("");setSidebarOpen(false);}
    } catch(e) {if(version===loadVersion.current) setError(e instanceof Error?e.message:"Түүх уншиж чадсангүй.");}
    finally {if(version===loadVersion.current) setLoadingHistory(false);}
  }
  async function send() {
    const text = question.trim();
    if (!text || sending.current || !user || loadingHistory) return;
    if(!retry.current || retry.current.text!==text || retry.current.conversation!==conversationId)
      retry.current={id: crypto.randomUUID(),text,conversation:conversationId};
    sending.current = true;
    setBusy(true);
    setError("");
    setQuestion("");
    const before = messages;
    setMessages((old) => [...old, { role: "user", content: text }]);
    try {
      const result = await api<{ answer: string; sources: Source[]; conversation_id: string }>("/chat", {
        question: text,
        conversation_id: conversationId,
        request_id: retry.current.id,
      });
      setConversationId(result.conversation_id);
      retry.current=null;
      setMessages([...before, {role:"user",content:text}, {role:"assistant",content:result.answer,sources:result.sources}]);
      try { await loadConversations(); } catch { setError("Хариулт хадгалагдсан. Ярианы жагсаалтыг шинэчлэхийн тулд хуудсыг дахин ачаална уу."); }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setMessages([]);
        router.replace("/login");
      } else {
        setError(e instanceof Error ? e.message : "Хариулт авч чадсангүй.");
        setMessages(before);
        setQuestion(text);
      }
    } finally {
      sending.current = false;
      setBusy(false);
    }
  }
  async function logout() {
    setLeaving(true);
    try {
      await api("/auth/logout", {});
      setMessages([]);
      router.replace("/login");
    } catch {
      setError("Гарч чадсангүй. Дахин оролдоно уу.");
      setLeaving(false);
    }
  }
  if (!user)
    return (
      <main className="login">
        {error ? (
          <Alert type="error" title={error} />
        ) : (
          <Spin description="Нэвтрэлтийг шалгаж байна…" />
        )}
      </main>
    );
  function newConversation() {
    loadVersion.current++;
    setConversationId(undefined); setMessages([]); setQuestion(""); setError("");
    retry.current=null; setSidebarOpen(false);
  }
  const sidebar = <>
    <div className="sidebar-heading">WHO туслах</div>
    <Button block size="large" onClick={newConversation} disabled={busy || loadingHistory || leaving}>＋ Шинэ яриа</Button>
    <div className="history-label">Өмнөх ярианууд</div>
    <nav className="history-list" aria-label="Чатын түүх">
      {!conversations.length && <p className="history-empty">Таны ярианууд энд хадгалагдана.</p>}
      {conversations.map(c => <button key={c.id} type="button"
        className={`history-item ${conversationId === c.id ? "active" : ""}`}
        aria-current={conversationId === c.id ? "page" : undefined}
        title={c.title} disabled={busy || loadingHistory || leaving}
        onClick={()=>void openConversation(c.id)}>{c.title}</button>)}
    </nav>
    <div className="sidebar-account"><span className="user-avatar" aria-hidden="true">{user.slice(0,1).toUpperCase()}</span><span className="account-name">{user}</span>
      <Button type="text" onClick={logout} loading={leaving} disabled={busy || loadingHistory}>Гарах</Button>
    </div>
  </>;
  return (
    <main className="chat-shell">
      <aside className="chat-sidebar">{sidebar}</aside>
      <Drawer title="Ярианууд" placement="left" open={sidebarOpen} onClose={()=>setSidebarOpen(false)} size={280} className="history-drawer">{sidebar}</Drawer>
      <div className="chat-main">
      <header className="chat-header">
        <Button className="sidebar-toggle" aria-label="Ярианы түүх нээх" onClick={()=>setSidebarOpen(true)}>☰</Button>
        <div><Typography.Title level={4} style={{margin:0}}>Эрүүл мэндийн туслах</Typography.Title>
        <Typography.Text type="secondary">WHO эх сурвалжтай асуулт, хариулт</Typography.Text></div>
      </header>
      <div className="chat-notice">
        <Alert
          type="warning"
          showIcon
          title="Ерөнхий мэдээлэл өгнө. Онош, эмчилгээг орлохгүй."
          description={<>Асуулт OpenAI руу илгээгдэнэ. <strong>Хувийн мэдээлэл бүү оруулаарай.</strong> Асуулт бүрийг тусад нь боловсруулна.</>}
        />
      </div>
      <section className="messages" aria-label="Чат" aria-live="polite">
        {loadingHistory && <div className="history-loading"><Spin description="Яриаг нээж байна…" /></div>}
        {!messages.length && !loadingHistory && (
          <div className="chat-welcome">
            <Typography.Title level={2}>Юу мэдэхийг хүсэж байна вэ?</Typography.Title>
            <p>Хүүхдийн хооллолт, хөхөөр хооллох зөвлөгөөний талаар асуугаарай.</p>
            <Button size="large" onClick={()=>setQuestion("Нэмэгдэл хоолыг хэдэн сартайгаас эхлүүлэх вэ?")}>Нэмэгдэл хоолыг хэзээнээс эхлүүлэх вэ?</Button>
          </div>
        )}
        {messages.map((m, i) => (
          <article
            key={i}
            className={`message ${m.role === "user" ? "user-message" : "assistant-message"}`}
            aria-label={m.role === "user" ? "Таны асуулт" : "Туслахын хариулт"}
          >
            <div>{m.content}</div>
            {!!m.sources?.length && (
              <div style={{ marginTop: 16 }}>
                <Typography.Text strong>Эх сурвалж</Typography.Text>
                {m.sources.map((s) => (
                  <div key={s.citation_id} style={{ marginTop: 8 }}>
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      [{s.citation_id}] {s.title}
                    </a>
                    <div>
                      <Typography.Text type="secondary">
                        {s.locator}
                      </Typography.Text>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </article>
        ))}
        {busy && <Spin description="Эх сурвалж хайж, хариулт бэлтгэж байна…" />}
        <div ref={end} />
      </section>
      <form
        className="composer"
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        {error && (
          <Alert
            type="error"
            title={error}
            showIcon
            closable
            onClose={() => setError("")}
            style={{ marginBottom: 12 }}
          />
        )}
        <Input.TextArea
          aria-label="Асуулт"
          placeholder="Асуултаа энд бичнэ үү…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={2000}
          autoSize={{ minRows: 2, maxRows: 6 }}
          onPressEnter={(e)=>{if(!e.shiftKey && !e.nativeEvent.isComposing){e.preventDefault();void send();}}}
          disabled={busy || leaving || loadingHistory}
        />
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginTop: 12,
            gap: 12,
          }}
        >
          <Typography.Text type="secondary">
            Enter — илгээх · Shift + Enter — шинэ мөр
          </Typography.Text>
          <Button
            type="primary"
            htmlType="submit"
            loading={busy}
            disabled={!question.trim() || leaving || loadingHistory}
          >
            Илгээх
          </Button>
        </div>
      </form>
      </div>
    </main>
  );
}
