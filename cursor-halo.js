// ── Cursor Halo Effect ──────────────────────────────────
// Adds a light-blue glowing orb that follows the cursor.
// Desktop only — no effect on touch devices.
(function () {
  // Skip on touch-only devices
  if ('ontouchstart' in window && !window.matchMedia('(pointer:fine)').matches) return;

  // Inject the halo element
  const halo = document.createElement('div');
  halo.id = 'cursor-halo';
  document.body.appendChild(halo);

  // Inject styles
  const style = document.createElement('style');
  style.textContent = `
    #cursor-halo {
      position: fixed;
      pointer-events: none;
      z-index: 9998;
      border-radius: 50%;
      transform: translate(-50%, -50%);
      transition: opacity 0.3s ease;
      opacity: 0;
      width: 80px;
      height: 80px;
      background: radial-gradient(circle, rgba(100,180,255,0.9) 0%, rgba(100,180,255,0) 100%);
      mix-blend-mode: overlay;
    }
    body:hover #cursor-halo { opacity: 1; }
  `;
  document.head.appendChild(style);

  // Smooth follow
  let hx = -200, hy = -200, tx = -200, ty = -200;

  document.addEventListener('mousemove', function (e) { tx = e.clientX; ty = e.clientY; });
  document.addEventListener('mouseleave', function () { halo.style.opacity = '0'; });
  document.addEventListener('mouseenter', function () { halo.style.opacity = '1'; });

  function animate() {
    hx += (tx - hx) * 0.15;
    hy += (ty - hy) * 0.15;
    halo.style.left = hx + 'px';
    halo.style.top = hy + 'px';
    requestAnimationFrame(animate);
  }
  animate();
})();
