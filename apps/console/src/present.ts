// Chế độ trình diễn (?present=1, console.md §4): chữ to, ẩn panel phụ, che chuỗi giống secret
export const presenting = new URLSearchParams(window.location.search).get("present") === "1";

// API key / token / bearer / connection string có mật khẩu: giữ vài ký tự đầu để người xem vẫn nhận ra loại
const SECRET_PATTERNS: RegExp[] = [
  /\b(sk|pk|rk|ghp|gho|xox[abpr]|dd[a-z]?)[-_][A-Za-z0-9_-]{12,}\b/g,
  /\bBearer\s+[A-Za-z0-9._~+/=-]{12,}/g,
  /(mongodb(?:\+srv)?:\/\/[^:/\s]+:)[^@\s]+@/g,
  /\b[a-f0-9]{32,}\b/gi,
  /\b[A-Za-z0-9+/_-]{40,}={0,2}(?![A-Za-z0-9])/g,
];

export function maskSecrets(text: string): string {
  let out = text;
  for (const re of SECRET_PATTERNS) {
    out = out.replace(re, (match: string, prefix?: string) =>
      typeof prefix === "string" && match.startsWith("mongodb") ? `${prefix}••••@` : `${match.slice(0, 4)}••••`,
    );
  }
  return out;
}

/** Che secret trong mọi text node đang hiển thị và cả nội dung render sau này (SSE, refetch). */
export function installSecretMask(root: Node = document.body): () => void {
  const scrub = (node: Node) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const before = node.nodeValue ?? "";
      const after = maskSecrets(before);
      if (after !== before) node.nodeValue = after; // chỉ ghi khi đổi → không lặp vô hạn
      return;
    }
    const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) scrub(n);
  };
  scrub(root);
  const observer = new MutationObserver((mutations) => {
    for (const m of mutations) {
      if (m.type === "characterData") scrub(m.target);
      m.addedNodes.forEach(scrub);
    }
  });
  observer.observe(root, { subtree: true, childList: true, characterData: true });
  return () => observer.disconnect();
}
