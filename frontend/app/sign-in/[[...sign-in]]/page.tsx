'use client';

import { useState } from 'react';
import { useSignIn } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { AuthCard } from '@/components/auth/AuthCard';


function clerkMessage(err: unknown): string {
  const e = err as { errors?: Array<{ longMessage?: string }>; message?: string };
  return e?.errors?.[0]?.longMessage || e?.message || '';
}

export default function SignInPage() {
  const { isLoaded, signIn, setActive } = useSignIn();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);

  // Send Email OTP via Clerk
  const handleSendOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoaded || !email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await signIn.create({
        identifier: email.trim(),
        strategy: 'email_code',
      });

      if (result.status === 'needs_first_factor') {
        setVerifying(true);
        startCooldown();
      }
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Failed to send OTP code. Please check your email.');
    } finally {
      setLoading(false);
    }
  };

  // Verify 6-digit OTP code via Clerk
  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoaded || !code.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await signIn.attemptFirstFactor({
        strategy: 'email_code',
        code: code.trim(),
      });

      if (result.status === 'complete') {
        await setActive({ session: result.createdSessionId });
        router.push('/dashboard');
      } else {
        setError('Verification incomplete. Please verify your OTP code.');
      }
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Invalid or expired OTP code.');
    } finally {
      setLoading(false);
    }
  };

  // Resend Email OTP code
  const handleResend = async () => {
    if (cooldown > 0 || !isLoaded) return;
    setError(null);
    setLoading(true);
    try {
      await signIn.create({
        identifier: email.trim(),
        strategy: 'email_code',
      });
      startCooldown();
    } catch {
      setError('Resend failed. Please try again in a few moments.');
    } finally {
      setLoading(false);
    }
  };

  // OAuth Google Sign-In
  const handleGoogleSignIn = async () => {
    if (!isLoaded) return;
    try {
      await signIn.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: '/sso-callback',
        redirectUrlComplete: '/dashboard',
      });
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Google sign-in initialization failed.');
    }
  };

  const startCooldown = () => {
    setCooldown(60);
    const interval = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);
  };

  return (
    <AuthCard
      mode="sign-in"
      verifying={verifying}
      email={email}
      code={code}
      loading={loading}
      error={error}
      cooldown={cooldown}
      onEmail={setEmail}
      onCode={setCode}
      onSubmitEmail={handleSendOTP}
      onSubmitCode={handleVerifyOTP}
      onGoogle={handleGoogleSignIn}
      onResend={handleResend}
      onChangeEmail={() => {
        setVerifying(false);
        setCode('');
        setError(null);
      }}
    />
  );
}
