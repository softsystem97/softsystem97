"""Historical shared theme only; recruitment writes are not imported."""

THEME = """
<style>
.ss97-m5{font-family:Outfit,system-ui,sans-serif;background:#020d1a;color:#cbd5e1;line-height:1.55;}
.ss97-m5 a{text-decoration:none;color:#a78bfa;}
.ss97-m5 h1,.ss97-m5 h2,.ss97-m5 h3{font-family:Space Grotesk,Outfit,sans-serif;color:#fff;font-weight:700;}
.ss97-m5 .wrap{width:min(1100px,92%);margin:0 auto;padding:48px 0;}
.ss97-m5 .hero{padding:56px 0 28px;background:radial-gradient(ellipse at 70% 0%,rgba(124,58,237,.35),transparent 55%),linear-gradient(165deg,#020d1a,#0a1428 60%,#1e1b4b);}
.ss97-m5 .hero h1{font-size:clamp(1.8rem,4vw,2.6rem);margin:0 0 10px;}
.ss97-m5 .hero p{color:#94a3b8;max-width:54ch;}
.ss97-m5 .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;}
.ss97-m5 .card{background:rgba(15,23,42,.75);border:1px solid rgba(148,163,184,.18);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:8px;}
.ss97-m5 .card:hover{border-color:rgba(124,58,237,.5);box-shadow:0 0 28px rgba(124,58,237,.2);}
.ss97-m5 .meta{font-size:.85rem;color:#94a3b8;}
.ss97-m5 .btns{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;}
.ss97-m5 .btn{display:inline-flex;padding:10px 16px;border-radius:10px;font-weight:600;font-size:.9rem;}
.ss97-m5 .btn-v{background:linear-gradient(135deg,#7c3aed,#6d28d9);color:#fff;}
.ss97-m5 .btn-b{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;}
.ss97-m5 .btn-g{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.2);color:#e2e8f0;}
.ss97-m5 .badge{display:inline-block;padding:4px 10px;border-radius:999px;background:rgba(124,58,237,.25);color:#c4b5fd;font-size:.75rem;font-weight:700;}
.ss97-m5 .filters{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0 24px;}
.ss97-m5 .filters input,.ss97-m5 .filters select{background:#0f172a;border:1px solid rgba(148,163,184,.25);color:#e2e8f0;border-radius:10px;padding:10px 12px;}
.ss97-m5 article.prose{background:rgba(15,23,42,.7);border:1px solid rgba(148,163,184,.15);border-radius:18px;padding:28px;}
.ss97-m5 article.prose p,.ss97-m5 article.prose li{color:#cbd5e1;}
@media(max-width:900px){.ss97-m5 .grid{grid-template-columns:1fr 1fr;}}
@media(max-width:575px){
  .ss97-m5 .grid{grid-template-columns:1fr;}
  .ss97-m5 .wrap{width:min(100%,96%);padding:28px 0 40px;}
  .ss97-m5 .hero{padding:36px 0 18px;}
  .ss97-m5 .btn{min-height:44px;justify-content:center;flex:1 1 auto;}
  .ss97-m5 .btns{gap:10px;}
  .ss97-m5 .filters input,.ss97-m5 .filters select,.ss97-m5 input,.ss97-m5 select,.ss97-m5 textarea{font-size:16px;min-height:44px;width:100%;box-sizing:border-box;}
  .ss97-m5 .card{padding:16px;}
  .ss97-m5 table{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;width:100%;}
}
</style>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;600;700&family=Space+Grotesk:wght@600;700&display=swap" rel="stylesheet">
"""
