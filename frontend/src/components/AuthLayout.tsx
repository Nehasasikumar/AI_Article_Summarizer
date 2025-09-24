import { ReactNode } from 'react';
import { useStore } from '../state';
import { Sun, Moon } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';

interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle: string;
}

export const AuthLayout = ({ children, title, subtitle }: AuthLayoutProps) => {
  const { theme, setTheme } = useStore();

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4 relative">
      {/* Theme Toggle - positioned at top right */}
      <div className="absolute top-4 right-4 flex items-center gap-2">
        <Sun className="w-4 h-4 text-yellow-500" />
        <Switch
          id="theme-switch-auth"
          checked={theme === 'dark'}
          onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
        />
        <Moon className="w-4 h-4 text-blue-500" />
      </div>

      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-foreground mb-2">{title}</h1>
          <p className="text-muted-foreground">{subtitle}</p>
        </div>

        <div className="bg-card rounded-2xl shadow-lg p-8 border border-accent/20">
          {children}
        </div>
      </div>
    </div>
  );
};
