"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, ArrowRight, Check, ChevronRight, FileText, Fingerprint, History, Loader2, LockKeyhole, LogOut, Menu, ScanSearch, ShieldCheck, Sparkles, UploadCloud, UserRound, X } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "https://red-cycles-marry.loca.lt";

type User = {
    id: string;
    email: string;
    full_name: string;
    role: string;
    is_active: boolean;
    created_at: string;
};

type Contract = {
    id: string;
    original_filename: string;
    mime_type: string;
    file_size_bytes: number;
    sha256_hash: string;
    contract_type: string;
    status: string;
    created_at: string;
};

type Verification = {
    contract_id: string;
    actual_sha256: string;
    result: string;
    duration_ms: number;
    risk_score: number;
    risk_label: string;
    ai_overview: string;
    ai_findings: Record<string, unknown>[];
};

type Log = {
    id: string;
    result: string;
    duration_ms: number;
    created_at: string;
};

async function api<T>(path: string, token?: string, options: RequestInit = {}): Promise<T> {
    const headers = new Headers(options.headers);
    if (token) headers.set("Authorization", `Bearer ${token}`);
    if (options.body && !(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
    const data = res.status === 204 ? null : await res.json().catch(() => null);
    if (!res.ok) {
        const detail = data?.detail;
        throw new Error(
            typeof detail === "string" ? detail : Array.isArray(detail) ? detail.map((x: any) => x.msg).join(", ") : `Yêu cầu thất bại (${res.status})`
        );
    }
    return data as T;
}

// Adapted from React Bits Spotlight Card. React Bits © David Haz, Commons Clause license.
function SpotlightCard({ children, className = "" }: { children: React.ReactNode; className?: string }) {
    const ref = useRef<HTMLDivElement>(null);
    const [p, setP] = useState({ x: 50, y: 20 });
    return (
        <div
            ref={ref}
            className={`spotlight-card ${className}`}
            style={{ "--spot-x": `${p.x}%`, "--spot-y": `${p.y}%` } as React.CSSProperties}
            onPointerMove={(e) => {
                const r = ref.current?.getBoundingClientRect();
                if (r) setP({ x: (e.clientX - r.left) / r.width * 100, y: (e.clientY - r.top) / r.height * 100 });
            }}
        >
            {children}
        </div>
    );
}

function DecryptedText({ text }: { text: string }) {
    const chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    const [value, setValue] = useState(text);
    useEffect(() => {
        if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
        let n = 0;
        const id = setInterval(() => {
            setValue(
                text
                    .split("")
                    .map((c, i) => (c === " " ? " " : i < n ? c : chars[Math.floor(Math.random() * chars.length)]))
                    .join("")
            );
            n += 0.8;
            if (n >= text.length) {
                setValue(text);
                clearInterval(id);
            }
        }, 38);
        return () => clearInterval(id);
    }, [text]);
    return <span>{value}</span>;
}

export default function Home() {
    const [token, setToken] = useState("");
    const [user, setUser] = useState<User | null>(null);
    const [authOpen, setAuthOpen] = useState(false);
    const [mode, setMode] = useState<"login" | "register">("login");
    const [busy, setBusy] = useState(false);
    const [file, setFile] = useState<File | null>(null);
    const [kind, setKind] = useState("rental");
    const [contract, setContract] = useState<Contract | null>(null);
    const [result, setResult] = useState<Verification | null>(null);
    const [logs, setLogs] = useState<Log[]>([]);
    const [dragging, setDragging] = useState(false);
    const [mobile, setMobile] = useState(false);

    useEffect(() => {
        const t = localStorage.getItem("contractguard_token") || "";
        if (t) {
            setToken(t);
            api<User>("/api/auth/me", t).then(setUser).catch(() => localStorage.removeItem("contractguard_token"));
        }
    }, []);

    const tone = useMemo(() => {
        if (!result) return "safe";
        return result.risk_score >= 70 ? "danger" : result.risk_score >= 40 ? "warning" : "safe";
    }, [result]);

    async function auth(e: React.FormEvent<HTMLFormElement>) {
        e.preventDefault();
        setBusy(true);
        const f = new FormData(e.currentTarget);
        try {
            if (mode === "register") {
                await api<User>("/api/auth/register", undefined, {
                    method: "POST",
                    body: JSON.stringify({ email: f.get("email"), password: f.get("password"), full_name: f.get("full_name") }),
                });
            }
            const login = await api<{ access_token: string }>("/api/auth/login", undefined, {
                method: "POST",
                body: JSON.stringify({ email: f.get("email"), password: f.get("password") }),
            });
            localStorage.setItem("contractguard_token", login.access_token);
            setToken(login.access_token);
            setUser(await api<User>("/api/auth/me", login.access_token));
            setAuthOpen(false);
            toast.success("Đăng nhập thành công");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : "Không thể đăng nhập");
        } finally {
            setBusy(false);
        }
    }

    async function analyze() {
        if (!token) {
            setAuthOpen(true);
            return;
        }
        if (!file) {
            toast.error("Vui lòng chọn một hợp đồng");
            return;
        }
        setBusy(true);
        setResult(null);
        try {
            const form = new FormData();
            form.append("file", file);
            const c = await api<Contract>("/api/contracts", token, {
                method: "POST",
                headers: { "contract-type": kind },
                body: form,
            });
            setContract(c);
            const v = await api<Verification>(`/api/contracts/${c.id}/verify`, token, { method: "POST", body: new FormData() });
            setResult(v);
            setLogs(await api<Log[]>(`/api/contracts/${c.id}/verifications`, token));
            toast.success("Đã phân tích hợp đồng");
        } catch (e) {
            toast.error(e instanceof Error ? e.message : "Không thể phân tích");
        } finally {
            setBusy(false);
        }
    }

    function pick(f?: File) {
        if (!f) return;
        if (!["application/pdf", "image/png", "image/jpeg"].includes(f.type)) {
            toast.error("Chỉ hỗ trợ PDF, PNG hoặc JPG");
            return;
        }
        setFile(f);
    }

    function logout() {
        localStorage.removeItem("contractguard_token");
        setToken("");
        setUser(null);
        setResult(null);
        toast.success("Đã đăng xuất");
    }

    return (
        <main className="app-shell">
            <div className="ambient-grid" />
            <div className="aurora aurora-a" />
            <div className="aurora aurora-b" />
            <nav className="topbar">
                <a className="brand" href="#top">
                    <span className="brand-mark">
                        <ShieldCheck size={21} />
                    </span>
                    <b>Contract<span>Guard</span></b>
                </a>
                <div className={`navlinks ${mobile ? "open" : ""}`}>
                    <a href="#analyze">Phân tích</a>
                    <a href="#workflow">Cách hoạt động</a>
                    <a href="#security">Bảo mật</a>
                </div>
                <div className="nav-actions">
                    {user ? (
                        <>
                            <span className="user-chip">
                                <UserRound size={15} />
                                {user.full_name}
                            </span>
                            <button className="icon-button" onClick={logout} aria-label="Đăng xuất">
                                <LogOut size={18} />
                            </button>
                        </>
                    ) : (
                        <button className="ghost-button" onClick={() => setAuthOpen(true)}>
                            Đăng nhập
                        </button>
                    )}
                    <button className="menu-button" onClick={() => setMobile(!mobile)} aria-label="Menu">
                        {mobile ? <X /> : <Menu />}
                    </button>
                </div>
            </nav>
            <section id="top" className="hero">
                <div className="hero-copy">
                    <div className="eyebrow">
                        <i /> Trợ lý hợp đồng dành cho sinh viên
                    </div>
                    <h1>
                        Đọc kỹ hợp đồng.
                        <br />
                        <DecryptedText text="Nhìn rõ rủi ro." />
                    </h1>
                    <p>
                        AI giúp bạn phát hiện điều khoản bất lợi, đối chiếu tính toàn vẹn và diễn giải hợp đồng bằng ngôn ngữ dễ hiểu — trước khi bạn đặt bút ký.
                    </p>
                    <div className="hero-actions">
                        <a className="primary-button" href="#analyze">
                            Kiểm tra hợp đồng <ArrowRight size={18} />
                        </a>
                        <a className="text-link" href="#workflow">
                            Cách hoạt động <ChevronRight size={16} />
                        </a>
                    </div>
                    <div className="trust-row">
                        <span>
                            <LockKeyhole /> Dữ liệu riêng tư
                        </span>
                        <span>
                            <Fingerprint /> SHA-256
                        </span>
                        <span>
                            <Sparkles /> Phân tích AI
                        </span>
                    </div>
                </div>
                <SpotlightCard className="risk-preview">
                    <div className="preview-top">
                        <span className="file-icon">
                            <FileText />
                        </span>
                        <div>
                            <b>hop-dong-thue-tro.pdf</b>
                            <small>12 trang · vừa phân tích</small>
                        </div>
                        <em>
                            <Check /> Toàn vẹn
                        </em>
                    </div>
                    <div className="score-ring">
                        <div>
                            <strong>68</strong>
                            <span>/100</span>
                            <small>Rủi ro cao</small>
                        </div>
                    </div>
                    <div className="preview-findings">
                        <div>
                            <span className="finding-icon red">
                                <AlertTriangle />
                            </span>
                            <p>
                                <b>Phí phạt chưa có giới hạn</b>
                                <small>Điều 8.2 có thể gây bất lợi.</small>
                            </p>
                            <ChevronRight />
                        </div>
                        <div>
                            <span className="finding-icon amber">
                                <ScanSearch />
                            </span>
                            <p>
                                <b>Điều khoản đặt cọc mơ hồ</b>
                                <small>Thiếu thời hạn hoàn trả cụ thể.</small>
                            </p>
                            <ChevronRight />
                        </div>
                    </div>
                    <div className="preview-foot">
                        <Sparkles /> AI chỉ hỗ trợ tham khảo, không thay thế tư vấn pháp lý.
                    </div>
                </SpotlightCard>
            </section>
            <section id="analyze" className="analyze-section">
                <div className="section-heading">
                    <span>01 / PHÂN TÍCH</span>
                    <h2>Tải hợp đồng của bạn lên</h2>
                    <p>Chọn loại hợp đồng để AI đặt rủi ro vào đúng bối cảnh.</p>
                </div>
                <div className="workspace">
                    <div className="type-selector">
                        {[
                            ["rental", "Thuê trọ", "Nhà ở, phòng trọ"],
                            ["internship", "Thực tập", "Lương, thời hạn"],
                            ["installment", "Trả góp", "Lãi suất, phí phạt"],
                            ["course", "Khóa học", "Hoàn phí, cam kết"],
                        ].map(([v, l, d]) => (
                            <button key={v} className={kind === v ? "active" : ""} onClick={() => setKind(v)}>
                                <span>{l}</span>
                                <small>{d}</small>
                                {kind === v && <Check />}
                            </button>
                        ))}
                    </div>
                    <div
                        className={`dropzone ${dragging ? "dragging" : ""}`}
                        onDragOver={(e) => {
                            e.preventDefault();
                            setDragging(true);
                        }}
                        onDragLeave={() => setDragging(false)}
                        onDrop={(e) => {
                            e.preventDefault();
                            setDragging(false);
                            pick(e.dataTransfer.files[0]);
                        }}
                    >
                        <input id="contract-file" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={(e) => pick(e.target.files?.[0])} />
                        <label htmlFor="contract-file">
                            <span className="upload-orb">
                                <UploadCloud />
                            </span>
                            {file ? (
                                <>
                                    <b>{file.name}</b>
                                    <small>{(file.size / 1048576).toFixed(2)} MB · Nhấn để đổi tệp</small>
                                </>
                            ) : (
                                <>
                                    <b>Kéo thả hợp đồng vào đây</b>
                                    <small>PDF, PNG, JPG · tối đa 20 MB</small>
                                </>
                            )}
                            <span className="browse-button">{file ? "Chọn tệp khác" : "Chọn tệp"}</span>
                        </label>
                    </div>
                    <button className="analyze-button" onClick={analyze} disabled={busy}>
                        {busy ? (
                            <>
                                <Loader2 className="spin" /> Đang đọc và phân tích…
                            </>
                        ) : (
                            <>
                                <ScanSearch /> Phân tích rủi ro ngay
                            </>
                        )}
                    </button>
                    {!user && <p className="signin-note"><LockKeyhole /> Bạn sẽ đăng nhập trước khi gửi tài liệu.</p>}
                </div>
            </section>
            {result && (
                <section className="results-section">
                    <div className="result-header">
                        <div>
                            <span>KẾT QUẢ PHÂN TÍCH</span>
                            <h2>{contract?.original_filename}</h2>
                            <p>{result.ai_overview || "Đã hoàn tất kiểm tra tính toàn vẹn và rủi ro."}</p>
                        </div>
                        <div className={`risk-badge ${tone}`}>
                            <strong>{result.risk_score}</strong>
                            <span>/100</span>
                            <small>{result.risk_label || "Mức rủi ro"}</small>
                        </div>
                    </div>
                    <div className="result-grid">
                        <SpotlightCard className="integrity-card">
                            <small>TÍNH TOÀN VẸN</small>
                            <ShieldCheck />
                            <h3>{result.result}</h3>
                            <p>Đối chiếu dấu vân tay số SHA-256.</p>
                            <code>{result.actual_sha256?.slice(0, 24)}…</code>
                        </SpotlightCard>
                        <div className="findings-card">
                            <div className="card-title">
                                <div>
                                    <small>AI FINDINGS</small>
                                    <h3>{result.ai_findings?.length || 0} điểm cần xem xét</h3>
                                </div>
                                <Sparkles />
                            </div>
                            {result.ai_findings?.length ? (
                                result.ai_findings.map((x, i) => (
                                    <div className="dynamic-finding" key={i}>
                                        <span>{i + 1}</span>
                                        <pre>{JSON.stringify(x, null, 2)}</pre>
                                    </div>
                                ))
                            ) : (
                                <div className="empty-finding">
                                    <Check /> Không có phát hiện chi tiết.
                                </div>
                            )}
                        </div>
                    </div>
                    {logs.length > 0 && (
                        <div className="history-card">
                            <div>
                                <History />
                                <span>
                                    <b>Lịch sử xác minh</b>
                                    <small>{logs.length} lần kiểm tra</small>
                                </span>
                            </div>
                            {logs.slice(0, 3).map((x) => (
                                <p key={x.id}>
                                    <span>{new Date(x.created_at).toLocaleString("vi-VN")}</span>
                                    <b>{x.result}</b>
                                    <small>{x.duration_ms} ms</small>
                                </p>
                            ))}
                        </div>
                    )}
                </section>
            )}
            <section id="workflow" className="workflow-section">
                <div className="section-heading">
                    <span>02 / QUY TRÌNH</span>
                    <h2>Ba bước để ký tự tin hơn</h2>
                </div>
                <div className="steps">
                    {[
                        ["01", UploadCloud, "Tải tài liệu", "PDF hoặc ảnh chụp rõ nét."],
                        ["02", Fingerprint, "Xác minh", "Kiểm tra toàn vẹn SHA-256."],
                        ["03", Sparkles, "Hiểu rủi ro", "AI chỉ ra điểm cần lưu ý."],
                    ].map(([n, I, t, d]) => (
                        <SpotlightCard key={n as string} className="step">
                            <span>{n as string}</span>
                            <I />
                            <h3>{t as string}</h3>
                            <p>{d as string}</p>
                        </SpotlightCard>
                    ))}
                </div>
            </section>
            <section id="security" className="security-banner">
                <span className="security-icon">
                    <ShieldCheck />
                </span>
                <div>
                    <small>THIẾT KẾ ƯU TIÊN AN TOÀN</small>
                    <h2>Hợp đồng của bạn là dữ liệu riêng tư.</h2>
                    <p>Phiên đăng nhập dùng Bearer token; tài liệu có dấu vân tay số riêng để phát hiện thay đổi.</p>
                </div>
                <div className="security-points">
                    <span>
                        <Check /> Token xác thực
                    </span>
                    <span>
                        <Check /> Băm SHA-256
                    </span>
                    <span>
                        <Check /> Quyền truy cập riêng
                    </span>
                </div>
            </section>
            <footer>
                <a className="brand" href="#top">
                    <span className="brand-mark">
                        <ShieldCheck />
                    </span>
                    <b>Contract<span>Guard</span></b>
                </a>
                <p>Hiểu rõ trước khi ký.</p>
                <small>Thông tin do AI cung cấp chỉ mang tính tham khảo.</small>
            </footer>
            <Dialog open={authOpen} onOpenChange={setAuthOpen}>
                <DialogContent className="auth-dialog">
                    <DialogHeader>
                        <div className="auth-mark">
                            <ShieldCheck />
                        </div>
                        <DialogTitle>{mode === "login" ? "Chào mừng trở lại" : "Tạo tài khoản miễn phí"}</DialogTitle>
                        <DialogDescription>
                            {mode === "login" ? "Đăng nhập để phân tích hợp đồng." : "Bắt đầu kiểm tra hợp đồng an toàn hơn."}
                        </DialogDescription>
                    </DialogHeader>
                    <form onSubmit={auth}>
                        {mode === "register" && (
                            <label>
                                Họ và tên
                                <input name="full_name" required placeholder="Nguyễn Văn An" />
                            </label>
                        )}
                        <label>
                            Email
                            <input name="email" type="email" required placeholder="ban@example.com" />
                        </label>
                        <label>
                            Mật khẩu
                            <input name="password" type="password" minLength={8} required placeholder="Tối thiểu 8 ký tự" />
                        </label>
                        <button className="primary-button full" disabled={busy}>
                            {busy ? (
                                <Loader2 className="spin" />
                            ) : (
                                mode === "login" ? "Đăng nhập" : "Đăng ký và tiếp tục"
                            )}
                        </button>
                    </form>
                    <p className="auth-switch">
                        {mode === "login" ? "Chưa có tài khoản?" : "Đã có tài khoản?"}{" "}
                        <button onClick={() => setMode(mode === "login" ? "register" : "login")}>
                            {mode === "login" ? "Đăng ký" : "Đăng nhập"}
                        </button>
                    </p>
                </DialogContent>
            </Dialog>
            <Toaster position="top-center" richColors />
        </main>
    );
}
