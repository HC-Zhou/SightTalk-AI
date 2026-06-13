import type { ButtonHTMLAttributes, ReactNode } from 'react';

interface IconButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  label: string;
  icon: ReactNode;
  active?: boolean;
}

export function IconButton({ label, icon, active = false, ...props }: IconButtonProps) {
  return (
    <button
      {...props}
      className={`icon-button${active ? ' is-active' : ''}`}
      title={label}
      aria-label={label}
      type={props.type ?? 'button'}
    >
      {icon}
    </button>
  );
}
