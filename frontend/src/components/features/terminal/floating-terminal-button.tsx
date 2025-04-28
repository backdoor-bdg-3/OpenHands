import React from "react";
import { useNavigate } from "react-router-dom";
import TerminalIcon from "#/icons/terminal.svg?react";
import { useTranslation } from "react-i18next";
import { I18nKey } from "#/i18n/declaration";
import { Tooltip } from "@heroui/react";

interface FloatingTerminalButtonProps {
  className?: string;
}

export function FloatingTerminalButton({ className = "" }: FloatingTerminalButtonProps) {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [isHovered, setIsHovered] = React.useState(false);
  const [position, setPosition] = React.useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = React.useState(false);
  const [initialPos, setInitialPos] = React.useState({ x: 0, y: 0 });
  const buttonRef = React.useRef<HTMLButtonElement>(null);
  
  React.useEffect(() => {
    const savedPosition = localStorage.getItem('terminalButtonPosition');
    if (savedPosition) {
      try {
        const parsedPosition = JSON.parse(savedPosition);
        setPosition(parsedPosition);
      } catch (e) {
        console.error('Failed to parse saved position', e);
      }
    }
  }, []);

  const handleClick = () => {
    if (!isDragging) {
      navigate("terminal");
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    
    setIsDragging(true);
    setInitialPos({
      x: e.clientX - position.x,
      y: e.clientY - position.y
    });
    
    e.preventDefault();
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (!isDragging) return;
    
    const newX = e.clientX - initialPos.x;
    const newY = e.clientY - initialPos.y;
    
    const buttonWidth = buttonRef.current?.offsetWidth || 0;
    const buttonHeight = buttonRef.current?.offsetHeight || 0;
    
    const maxX = window.innerWidth - buttonWidth;
    const maxY = window.innerHeight - buttonHeight;
    
    const boundedX = Math.max(0, Math.min(newX, maxX));
    const boundedY = Math.max(0, Math.min(newY, maxY));
    
    setPosition({ x: boundedX, y: boundedY });
  };

  const handleMouseUp = () => {
    if (isDragging) {
      setIsDragging(false);
      localStorage.setItem('terminalButtonPosition', JSON.stringify(position));
    }
  };

  React.useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, initialPos]);

  const buttonStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: position.y === 0 ? '1.5rem' : 'auto',
    right: position.x === 0 ? '1.5rem' : 'auto',
    top: position.y !== 0 ? position.y + 'px' : 'auto',
    left: position.x !== 0 ? position.x + 'px' : 'auto',
    cursor: isDragging ? 'grabbing' : 'grab',
    zIndex: 50,
  };

  return (
    <Tooltip content={isDragging ? t("Drag to reposition") : t(I18nKey.WORKSPACE$TERMINAL_TAB_LABEL)}>
      <button
        ref={buttonRef}
        type="button"
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onMouseDown={handleMouseDown}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
        onFocus={() => setIsHovered(true)}
        onBlur={() => setIsHovered(false)}
        style={buttonStyle}
        className={`p-3 rounded-full bg-tertiary border border-neutral-600 shadow-lg hover:bg-tertiary-dark focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-tertiary-light transition-all duration-200 ${
          isHovered && !isDragging ? 'scale-110' : 'scale-100'
        } ${className}`}
        aria-label={t(I18nKey.WORKSPACE$TERMINAL_TAB_LABEL)}
        tabIndex={0}
      >
        <TerminalIcon className="w-6 h-6" />
      </button>
    </Tooltip>
  );
}

export default FloatingTerminalButton;
