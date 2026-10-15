'use client';

import { useState } from 'react';
import { useSignUp } from '@clerk/nextjs';
import { useRouter } from 'next/navigation';
import { AuthCard } from '@/components/auth/AuthCard';


function clerkMessage(err: unknown): string {
  const e = err as { errors?: Array<{ longMessage?: string }>; message?: string };
  return e?.errors?.[0]?.longMessage || e?.message || '';
}

export default function SignUpPage() {
  const { isLoaded, signUp, setActive } = useSignUp();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [verifying, setVerifying] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Send Email OTP via Clerk Sign-Up
  const handleStartSignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoaded || !email.trim()) return;

    setLoading(true);
    setError(null);

    try {
      await signUp.create({
        emailAddress: email.trim(),
      });

      await signUp.prepareEmailAddressVerification({
        strategy: 'email_code',
      });

      setVerifying(true);
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Failed to initiate sign-up OTP code.');
    } finally {
      setLoading(false);
    }
  };

  // Verify 6-digit OTP code via Clerk Sign-Up
  const handleVerifySignUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!isLoaded || !code.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const result = await signUp.attemptEmailAddressVerification({
        code: code.trim(),
      });

      if (result.status === 'complete') {
        await setActive({ session: result.createdSessionId });
        router.push('/dashboard');
      } else {
        setError('Sign-up incomplete. Please complete email verification.');
      }
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Invalid or expired OTP code.');
    } finally {
      setLoading(false);
    }
  };

  // Google OAuth Sign-Up
  const handleGoogleSignUp = async () => {
    if (!isLoaded) return;
    try {
      await signUp.authenticateWithRedirect({
        strategy: 'oauth_google',
        redirectUrl: '/sso-callback',
        redirectUrlComplete: '/dashboard',
      });
    } catch (err: unknown) {
      setError(clerkMessage(err) || 'Google sign-up initialization failed.');
    }
  };

  return (
    <AuthCard
      mode="sign-up"
      verifying={verifying}
      email={email}
      code={code}
      loading={loading}
      error={error}
      
      onEmail={setEmail}
      onCode={setCode}
      onSubmitEmail={handleStartSignUp}
      onSubmitCode={handleVerifySignUp}
      onGoogle={handleGoogleSignUp}
      
      onChangeEmail={() => {
        setVerifying(false);
        setCode('');
        setError(null);
      }}
    />
  );
}
