import { create } from 'zustand';

interface User {
  name: string;
  email: string;
}

interface Store {
  user: User | null;
  theme: 'light' | 'dark';
  setUser: (user: User | null) => void;
  setTheme: (theme: 'light' | 'dark') => void;
}

export const useStore = create<Store>((set) => ({
  user: null,
  theme: (localStorage.getItem('theme') as 'light' | 'dark') || 'light',
  setUser: (user) => set({ user }),
  setTheme: (theme) => {
    localStorage.setItem('theme', theme);
    set({ theme });
  },
}));
