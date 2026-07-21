import type { ReactNode } from "react";

type AuthShellProps = {
  eyebrow: string;
  title: string;
  description: string;
  children: ReactNode;
};

export function AuthShell({ eyebrow, title, description, children }: AuthShellProps) {
  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="brand brand-auth">
          <span className="brand-mark">A</span>
          <span className="brand-copy">
            <strong>Avpilot</strong>
            <small>星航仪</small>
          </span>
        </div>
        <div className="story-copy">
          <p className="eyebrow">你的 AI 知识领航系统</p>
          <h1>让课题组的知识，<br />成为可追溯的共同记忆。</h1>
          <p>汇集论文、实验记录与项目资料，在可靠引用的基础上检索、理解和延续知识。</p>
        </div>
        <div className="story-orbit" aria-hidden="true">
          <span className="orbit orbit-one" />
          <span className="orbit orbit-two" />
          <span className="orbit-core">AVP</span>
        </div>
      </section>
      <section className="auth-panel">
        <div className="auth-card">
          <p className="eyebrow">{eyebrow}</p>
          <h2>{title}</h2>
          <p className="auth-description">{description}</p>
          {children}
        </div>
      </section>
    </main>
  );
}
