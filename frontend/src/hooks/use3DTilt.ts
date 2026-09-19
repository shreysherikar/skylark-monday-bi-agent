import { useState, useRef, useCallback } from 'react';

interface TiltStyle {
  transform: string;
  glareStyle?: React.CSSProperties;
}

export function use3DTilt(maxTilt = 10, scale = 1.02) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [tiltStyle, setTiltStyle] = useState<TiltStyle>({
    transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)',
    glareStyle: {
      opacity: 0,
      background: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.2) 0%, transparent 60%)',
    },
  });

  const onMouseMove = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      if (!ref.current) return;
      const rect = ref.current.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;

      const rotX = ((y - 0.5) * -maxTilt).toFixed(2);
      const rotY = ((x - 0.5) * maxTilt).toFixed(2);

      setTiltStyle({
        transform: `perspective(1000px) rotateX(${rotX}deg) rotateY(${rotY}deg) scale3d(${scale}, ${scale}, ${scale})`,
        glareStyle: {
          opacity: 0.65,
          background: `radial-gradient(circle at ${(x * 100).toFixed(0)}% ${(y * 100).toFixed(0)}%, rgba(56, 189, 248, 0.28) 0%, rgba(0, 217, 255, 0.08) 35%, transparent 70%)`,
        },
      });
    },
    [maxTilt, scale]
  );

  const onMouseLeave = useCallback(() => {
    setTiltStyle({
      transform: 'perspective(1000px) rotateX(0deg) rotateY(0deg) scale3d(1, 1, 1)',
      glareStyle: {
        opacity: 0,
        background: 'radial-gradient(circle at 50% 50%, rgba(255,255,255,0.2) 0%, transparent 60%)',
      },
    });
  }, []);

  return { ref, tiltStyle, onMouseMove, onMouseLeave };
}
