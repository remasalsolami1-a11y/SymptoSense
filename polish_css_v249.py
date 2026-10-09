"""CSS for the V249 result first screen, contrast fixes and the V251 emergency stop overlay.

Kept out of webapp.py to respect the monolith size guard."""
CSS = r"""
/* V249 result first screen */
.ss-emergency-strip{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:12px 0 0;padding:12px 14px;border-radius:14px;background:#FFF8E6;border:1px solid #F1DFA6}
.ss-emergency-strip.urgent{background:#FFF1F1;border-color:#E9A5A5}
.ss-emergency-strip p{margin:0;flex:1 1 220px;font-size:13px;line-height:1.7}
.ss-call-btn{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:48px;padding:0 18px;border-radius:12px;background:#C62828;color:#fff!important;font-weight:800;text-decoration:none}
.ss-disclaimer{margin:10px 2px 0;font-size:12.5px;line-height:1.7;color:#4B6074}
.ss-details-divider{display:flex;align-items:center;gap:10px;margin:18px 0 6px;color:#4B6074;font-size:13px;font-weight:800}
.ss-details-divider:before,.ss-details-divider:after{content:"";flex:1;height:1px;background:#D5E2EA}
/* V249 contrast fixes (WCAG AA) found by the full-flow axe audit */
body.ss-chat-page .chat-head{background:#1F6FAE!important}
body.ss-chat-page #famSelect{background:rgba(0,0,0,.22)!important}
body.ss-chat-page .chat-head h3,body.ss-chat-page .chat-head p{color:#fff!important}
body.ss-chat-page .ss-quality-score,body.ss-chat-page a.ss-step-source{color:#1F6FAE!important}
/* V251 stronger emergency stop */
.em-overlay{background:rgba(127,29,29,.72)!important}
.em-card{max-width:520px!important;text-align:start!important}
.em-card h3,.em-card>p,.em-card .em-icon{text-align:center}
.em-card .em-icon{margin-inline:auto}
.em-card .em-flags,.em-card .em-btns{justify-content:center}
.em-call-main{font-size:18px!important;min-height:54px;display:inline-flex;align-items:center;padding:0 26px!important;animation:emPulse 1.6s ease-in-out infinite}
.em-call-alt{background:#7F1D1D!important}
.em-back{background:#B91C1C!important}
@keyframes emPulse{0%,100%{box-shadow:0 0 0 0 rgba(220,38,38,.55)}50%{box-shadow:0 0 0 12px rgba(220,38,38,0)}}
@media (prefers-reduced-motion:reduce){.em-call-main{animation:none}}
.em-steps{background:#FEF2F2;border:1px solid #FECACA;border-radius:14px;padding:12px 16px;margin:14px 0}
.em-steps-t{font-weight:800;color:#991B1B;margin-bottom:6px}
.em-steps ol{margin:0;padding-inline-start:22px;line-height:1.9;font-size:14.5px;color:#1F2937}
.em-confirm{margin-top:10px;padding:12px;border:1px dashed #c81e1e;border-radius:12px;text-align:center}
.em-confirm[hidden],.em-exit[hidden]{display:none!important}
.em-ghost{background:transparent!important;color:#4B5563!important;font-weight:600!important;font-size:13px!important}
body.ss-em-open{overflow:hidden}
/* V261 contrast (WCAG AA): later generic rules were overriding these colours on wide screens */
.nav .links a.v2-nav-cta,.nav .links a.v2-nav-cta:hover{background:#1b66a3!important;color:#fff!important}
#famSelect,body.ss-chat-page #famSelect{background:#fff!important;color:#0F2F63!important;border:1px solid #fff!important;font-weight:700}
.f-tg,.f-tg:hover,.footer .f-tg,.footer .f-tg:hover{background:#1b66a3!important;color:#fff!important}
.footer .f-love b,.footer .f-brand span{color:#1d5f99!important}
/* V261 legibility floor: no UI text under 12px (safety banner, step label, bottom-nav labels, chat sub-title) */
body #ssOfflineBanner small{font-size:12.5px!important;line-height:1.6!important}
body #ssOfflineBanner a{font-size:13px!important;min-height:44px;display:inline-flex;align-items:center}
body.ss-chat-page #headP{font-size:12px!important;color:#fff!important}
body .ss-flow-copy span,body.ss-chat-page .ss-flow-copy span{font-size:12px!important}
body #ssBnav a span,body .ss-bnav a span{font-size:12px!important;font-weight:700;line-height:1.2}
body.ss-chat-page .chat-access>summary{min-height:44px;display:inline-flex;align-items:center}
.lang-sw a{min-height:40px;display:inline-flex;align-items:center}
body .account-label,body .account-menu-head small{font-size:12px!important}
body .ss-trust-item,body .ss-trust-ic,body .ss-trust-safety-link span,body .ss-hero-kicker b,body .ss-tech-card b,body .ss-v132-privacy b,body .ss-tools-all,body .ss-tool small,body .ss-how-step small,body .ss-source-more,body .ss-source-badge,body .ss-strength-stat span,body .ss-strength-note,body .ss-strength-note a,body .eyebrow{font-size:12px!important}
/* V262 legibility floor, part 2: demo card, privacy notes, medication time labels (>= 12px) */
body .ss-result-risk em,body .ss-result-risk small,body .ss-mini-row small,body .ss-mini-row b,body .ss-next-panel p,body .ss-source-logos span,body .ss-source-panel a,body .ss-tech-card small,body .ss-demo-note{font-size:12px!important;line-height:1.5}
body .ss-tech-card b,body .ss-mini-panel h3{font-size:12.5px!important}
body .ss-demo-note{width:130px}
body .med-time-field>small,body .med-time-field small{font-size:12px!important;font-weight:700;color:#475569}
body label small,body .consent small,body [class*="consent"] small,body [class*="privacy"] small,body .bconsent small,body .form-note,body .field-note{font-size:12px!important;line-height:1.7}
/* V262 part 3: small-viewport media rules were out-specifying the floor above */
html body .ss-mobile-account span,html body .ss-hero-kicker span,html body .ss-hero-kicker b,html body .ss-trust-row .ss-trust-item,html body .ss-tech-card b,html body .ss-v132-privacy b,html body .ss-result-risk em,html body .ss-result-risk small,html body .ss-mini-row small,html body .ss-mini-row span,html body .ss-mini-row b,html body .ss-core-card p,html body .ss-tools-head .ss-tools-all,html body .ss-tool small,html body .ss-strength-stat span,html body .ss-how-step small,html body .ss-how-step .ss-how-num,html body .ss-source-badge,html body .ss-source-logos span,html body .ss-next-panel p{font-size:12px!important;line-height:1.5}
html body .ss-how-step .ss-how-num{min-width:22px}
html body .ss-mini-row span{font-size:14px!important}
html body label.med-time-field small,html body .bconsent small,html body #bloodCollectConsent~label small,html body .consent-note,html body label small{font-size:12px!important}
/* V262 part 4: home inline CSS uses body.ss-home-page + !important; match with a stronger selector */
html body.ss-home-page.ss-home-page .ss-tech-card b,html body.ss-home-page.ss-home-page .ss-v132-privacy b,html body.ss-home-page.ss-home-page .ss-result-risk em,html body.ss-home-page.ss-home-page .ss-result-risk small,html body.ss-home-page.ss-home-page .ss-mini-row small,html body.ss-home-page.ss-home-page .ss-mini-row b,html body.ss-home-page.ss-home-page .ss-core-card p,html body.ss-home-page.ss-home-page .ss-tool small,html body.ss-home-page.ss-home-page .ss-strength-stat span,html body.ss-home-page.ss-home-page .ss-how-step small,html body.ss-home-page.ss-home-page .ss-how-step .ss-how-num,html body.ss-home-page.ss-home-page .ss-source-badge,html body.ss-home-page.ss-home-page .ss-source-logos span,html body.ss-home-page.ss-home-page .ss-next-panel p,html body.ss-home-page.ss-home-page .ss-source-panel a,html body.ss-home-page.ss-home-page .ss-tools-head .ss-tools-all,html body.ss-home-page.ss-home-page .ss-trust-row .ss-trust-item,html body.ss-home-page.ss-home-page .ss-hero-kicker b,html body.ss-home-page.ss-home-page .ss-demo-note{font-size:12px!important;line-height:1.5}
/* V262 part 5: page-local notes */
html body .delivery-note,html body .lab-page-add-note,html body #labPageHint,html body .camera-review small{font-size:12px!important;line-height:1.7}
"""
