import React, { useState } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { firebaseApp, firebaseAuth } from "../app";
import { apiClient } from "../app";
import { signInWithEmailAndPassword, createUserWithEmailAndPassword, updateProfile, sendPasswordResetEmail } from 'firebase/auth';
import { getFirestore, doc, setDoc, Timestamp } from 'firebase/firestore';
import { COLLECTIONS, User } from "../utils/firestore-schema";
import { toast } from 'sonner';

export default function Login() {
  const navigate = useNavigate();
  const location = useLocation();

  // State to toggle between login, registration, and password reset
  const [isRegistering, setIsRegistering] = useState(false);
  const [isResettingPassword, setIsResettingPassword] = useState(false);

  // Login form state
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  // Registration form state
  const [displayName, setDisplayName] = useState('');
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [company, setCompany] = useState('');
  const [location_, setLocation_] = useState('');
  const [selectedRole, setSelectedRole] = useState<'technician' | 'company_admin'>('technician');
  const [resetEmail, setResetEmail] = useState('');
  const [useDirectApproval, setUseDirectApproval] = useState(false); // For testing only

  const [isLoading, setIsLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // Get the redirect URL from query params if available
  const queryParams = new URLSearchParams(location.search);
  const redirectPath = queryParams.get('next') || '/';
  const shouldRegister = queryParams.get('register') === 'true';

  // Set registration mode if query param is present
  React.useEffect(() => {
    if (shouldRegister && !isRegistering && !isResettingPassword) {
      toggleMode('register');
    }
  }, [shouldRegister, isRegistering, isResettingPassword]);

  // Initialize Firestore
  const firestore = getFirestore(firebaseApp);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    // Basic form validation
    if (!email.trim()) {
      setFormError('Email is required');
      return;
    }

    if (!password) {
      setFormError('Password is required');
      return;
    }

    try {
      setIsLoading(true);
      setFormError(null);

      // Sign in with Firebase Auth
      await signInWithEmailAndPassword(firebaseAuth, email, password);

      // Update lastActive timestamp
      if (firebaseAuth.currentUser) {
        const userRef = doc(firestore, COLLECTIONS.USERS, firebaseAuth.currentUser.uid);
        await setDoc(userRef, { lastActive: Timestamp.now() }, { merge: true });
      }

      // Show success toast
      toast.success('Signed in successfully');

      // Redirect user
      navigate(redirectPath);
    } catch (error: any) {
      // Firebase error messages are usually too technical for users
      // So we'll display a more user-friendly message
      if (error.code === 'auth/user-not-found' || error.code === 'auth/wrong-password') {
        setFormError('Invalid email or password');
      } else if (error.code === 'auth/too-many-requests') {
        setFormError('Too many failed login attempts. Please try again later.');
      } else {
        setFormError('Failed to sign in. Please try again.');
      }
      console.error('Login error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleForgotPassword = (e: React.MouseEvent) => {
    e.preventDefault();
    toggleMode('reset');
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();

    // Basic form validation
    if (!resetEmail.trim()) {
      setFormError('Email is required');
      return;
    }

    try {
      setIsLoading(true);
      setFormError(null);

      // Send password reset email using Firebase
      await sendPasswordResetEmail(firebaseAuth, resetEmail);

      // Show success toast
      toast.success('Password reset email sent. Check your inbox.');

      // Return to login form
      toggleMode('login');
    } catch (error: any) {
      console.error('Password reset error:', error);

      // Handle Firebase error codes
      if (error.code === 'auth/user-not-found') {
        setFormError('No account found with this email address.');
      } else if (error.code === 'auth/invalid-email') {
        setFormError('Invalid email address. Please check and try again.');
      } else if (error.code === 'auth/too-many-requests') {
        setFormError('Too many password reset attempts. Please try again later.');
      } else {
        setFormError('Failed to send password reset email. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();

    // Basic form validation
    if (!displayName.trim()) {
      setFormError('Name is required');
      return;
    }

    if (!registerEmail.trim()) {
      setFormError('Email is required');
      return;
    }

    if (registerPassword.length < 6) {
      setFormError('Password must be at least 6 characters');
      return;
    }

    if (registerPassword !== confirmPassword) {
      setFormError('Passwords do not match');
      return;
    }

    // Add check for company admin role
    if (selectedRole === 'company_admin' && !company.trim()) {
      setFormError('Company name is required for Company Admin role');
      return;
    }

    try {
      setIsLoading(true);
      setFormError(null);

      if (useDirectApproval) {
        // Use direct API registration approach (for testing)
        console.log('Using direct registration API for improved permissions handling');
        
        try {
          // Using direct registration API with force_recreate option to handle existing users
          const registerResponse = await (apiClient as any).register_user({
            email: registerEmail,
            password: registerPassword,
            displayName: displayName,
            role: selectedRole,
            company: company.trim() || undefined,
            location: location_.trim() || undefined,
            force_recreate: true // For testing, allow recreating users with the same email
          });

          // Check the response
          const responseData = await registerResponse.json();
          console.log('Direct registration API response:', responseData);
          
          // Handle response based on success flag
          if (responseData && responseData.success === true && responseData.userId) {
            // Success case - using userId from response
            let successMessage = responseData.message || "Account created successfully!";
            
            // Add role-specific guidance for pending accounts
            if (selectedRole === "company_admin" && successMessage.includes("pending")) {
              successMessage += " A System Admin needs to approve your account before you can log in.";
            } else if (selectedRole === "technician" && successMessage.includes("pending")) {
              successMessage += " A Company Admin needs to approve your account before you can log in.";
            }
            
            toast.success(successMessage);
            
            try {
              // Sign in with the new credentials
              await signInWithEmailAndPassword(firebaseAuth, registerEmail, registerPassword);
              
              // Force token refresh to immediately get updated custom claims
              if (firebaseAuth.currentUser) {
                console.log('Forcing token refresh to get updated custom claims');
                await firebaseAuth.currentUser.getIdToken(true);
              }
              
              // Redirect to home
              navigate('');
              return;
            } catch (signInError: any) {
              console.error('Error signing in after registration:', signInError);
              // Continue to show success message but also warn about login issue
              toast.error('Account created but unable to sign in automatically. Please try signing in manually.');
              
              // Switch to login view for convenience
              toggleMode('login');
              // Pre-fill email field for login
              setEmail(registerEmail);
              return;
            }
          } else {
            // API returned success=false or missing userId
            const errorMsg = responseData?.message || 'Registration failed for unknown reason';
            console.error('Registration failed:', errorMsg);
            throw new Error(errorMsg);
          }
        } catch (error: any) {
          console.error('Direct registration API error:', error);
          
          // More detailed error logging
          console.log('Error type:', typeof error);
          
          // Enhanced error handling with specific user-friendly messages
          try {
            // Handle HTTP errors
            if (error.status) {
              console.log('HTTP error status:', error.status);
              try {
                const errorData = await error.json().catch(() => null);
                console.log('Error response data:', errorData);
                
                // Extract error message from response
                const errorMessage = errorData?.message || errorData?.detail || 'Server error during registration';
                setFormError(errorMessage);
              } catch (parseError) {
                console.error('Error parsing HTTP error response:', parseError);
                setFormError(`Server error (${error.status}): Please try again later.`);
              }
            }
            // Handle Firebase Auth errors (when trying to signIn after registration)
            else if (error.code && error.code.startsWith('auth/')) {
              console.log('Firebase Auth error code:', error.code);
              
              // Map Firebase error codes to user-friendly messages
              if (error.code === 'auth/email-already-in-use') {
                setFormError('This email is already registered. Please use a different email or sign in.');
              } else if (error.code === 'auth/invalid-email') {
                setFormError('Please enter a valid email address.');
              } else if (error.code === 'auth/weak-password') {
                setFormError('Please choose a stronger password (at least 6 characters).');
              } else if (error.code === 'auth/network-request-failed') {
                setFormError('Network error. Please check your internet connection and try again.');
              } else {
                setFormError('Authentication error: ' + error.message);
              }
            }
            // Handle general JS errors with message property
            else if (error.message) {
              console.log('Error message:', error.message);
              setFormError(error.message);
            }
            // Fallback for unexpected error formats
            else {
              console.log('Unhandled error format:', error);
              setFormError('Registration failed. Please try again later.');
            }
          } catch (handlingError) {
            // Last resort fallback if error handling itself fails
            console.error('Error while handling registration error:', handlingError);
            setFormError('Registration failed. Please try again later.');
          }
          
          setIsLoading(false);
          return;
        }
      }

      // Regular Firebase client registration
      try {
        console.log('No user logged in, defaulting to technician role');
        // 1. Create Firebase Auth account
        const userCredential = await createUserWithEmailAndPassword(
          firebaseAuth, 
          registerEmail, 
          registerPassword
        );

        const user = userCredential.user;

        // 2. Update display name in Firebase Auth
        await updateProfile(user, {
          displayName: displayName,
        });

        // 3. Create user profile in Firestore
        const now = Timestamp.now();
        const userProfile: User = {
          uid: user.uid,
          email: user.email!,
          displayName: displayName,
          role: selectedRole,
          approvalStatus: 'pending_approval', // All new users start with pending approval
          createdAt: now,
          lastActive: now,
        };

        // Add optional fields if provided
        if (company.trim()) {
          userProfile.company = company.trim();
        }

        // Save profile to Firestore
        await setDoc(doc(firestore, COLLECTIONS.USERS, user.uid), userProfile);

        // Create a pending request for approval
        const pendingRequestData = {
          id: user.uid, // Use user ID as request ID
          uid: user.uid,
          userEmail: user.email!,
          displayName: displayName,
          requestedRole: selectedRole,
          company: company.trim() || null,
          requestedAt: now,
          status: 'pending'
        };

        await setDoc(doc(firestore, COLLECTIONS.PENDING_REQUESTS, user.uid), pendingRequestData);

        // Show success toast and inform about pending approval
        toast.success('Account created successfully');
        toast.info('Your account is pending approval. You will be notified once approved.');

        // Redirect to home
        navigate('');
      } catch (error: any) {
        // Check for missing permissions error
        if (error.message?.includes('Missing or insufficient permissions')) {
          setUseDirectApproval(true);
          toast.error('Direct Firestore access is restricted. Will use API on next attempt.');
          setFormError('Please try submitting the form again.');
        } else {
          // Handle other errors
          if (error.code === 'auth/email-already-in-use') {
            setFormError('Email already in use. Please use a different email or sign in.');
          } else if (error.code === 'auth/invalid-email') {
            setFormError('Invalid email address. Please check and try again.');
          } else if (error.code === 'auth/weak-password') {
            setFormError('Password is too weak. Please choose a stronger password.');
          } else {
            setFormError('Failed to register. Please try again.');
          }
          console.error('Registration error:', error);
        }
      }
    } catch (error: any) {
      // Handle Firebase error codes
      if (error.code === 'auth/email-already-in-use') {
        setFormError('Email already in use. Please use a different email or sign in.');
      } else if (error.code === 'auth/invalid-email') {
        setFormError('Invalid email address. Please check and try again.');
      } else if (error.code === 'auth/weak-password') {
        setFormError('Password is too weak. Please choose a stronger password.');
      } else {
        setFormError('Failed to register. Please try again.');
      }
      console.error('Registration error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Clear form error when switching between modes
  const toggleMode = (mode: 'login' | 'register' | 'reset') => {
    console.log('Toggling mode to:', mode);
    setFormError(null);

    if (mode === 'login') {
      setIsRegistering(false);
      setIsResettingPassword(false);
      console.log('Setting isRegistering to false');
    } else if (mode === 'register') {
      setIsRegistering(true);
      setIsResettingPassword(false);
      console.log('Setting isRegistering to true');
    } else if (mode === 'reset') {
      setIsRegistering(false);
      setIsResettingPassword(true);
      // Pre-fill reset email if login email is set
      if (email && !resetEmail) {
        setResetEmail(email);
      }
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="py-4 px-4 bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto flex items-center justify-between">
          <div className="flex items-center">
            <JuniorTechBotLogo className="w-8 h-8 mr-2" />
            <h1 className="text-xl font-bold">
              <span className="text-white">Junior</span>
              <span className="text-blue-400">TechBot</span>
            </h1>
          </div>
          <nav>
            <ul className="flex space-x-4">
              <li>
                <Link to="/" className="text-gray-300 hover:text-white">
                  Home
                </Link>
              </li>
              <li>
                <button 
                  onClick={() => toggleMode(isRegistering ? 'login' : 'register')}
                  className="text-gray-300 hover:text-white bg-transparent border-0 p-0 cursor-pointer"
                >
                  {isRegistering ? 'Login' : 'Register'}
                </button>
              </li>
            </ul>
          </nav>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 container mx-auto py-8 px-4 flex items-center justify-center">
        <div className="w-full max-w-md">
          <div className="bg-gray-800 rounded-lg p-8 shadow-lg border border-gray-700">
            <div className="text-center mb-8">
              <JuniorTechBotLogo className="w-16 h-16 mx-auto mb-4" />
              <h2 className="text-2xl font-bold">
                Welcome to
                <span className="text-white"> Junior</span>
                <span className="text-blue-400">TechBot</span>
              </h2>
              <p className="text-gray-400 mt-2">
                {isResettingPassword ? 'Reset your password' : isRegistering ? 'Create your account' : 'Sign in to your account'}
              </p>
            </div>

            {/* Toggle between login, register and reset password */}
            <div className="flex mb-6 border-b border-gray-700">
              <button 
                className={`flex-1 py-2 text-center ${!isRegistering && !isResettingPassword ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-300'}`}
                onClick={() => toggleMode('login')}
                type="button"
              >
                Sign In
              </button>
              <button 
                className={`flex-1 py-2 text-center ${isRegistering ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400 hover:text-gray-300'}`}
                onClick={() => toggleMode('register')}
                type="button"
              >
                Create Account
              </button>
            </div>

            {formError && (
              <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-md text-red-400 text-sm">
                {formError}
              </div>
            )}

            {isResettingPassword ? (
              /* Password Reset Form */
              <form onSubmit={handleResetPassword}>
                <div className="mb-6">
                  <label htmlFor="resetEmail" className="block text-gray-300 mb-2">
                    Email Address
                  </label>
                  <input
                    type="email"
                    id="resetEmail"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="your.email@example.com"
                    value={resetEmail}
                    onChange={(e) => setResetEmail(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <Button
                  type="submit"
                  variant="default"
                  className="w-full"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Sending reset email...
                    </>
                  ) : 'Send Password Reset Email'}
                </Button>

                <div className="mt-6 text-center text-gray-400">
                  <p>
                    <button
                      type="button"
                      onClick={() => toggleMode('login')}
                      className="text-blue-400 hover:text-blue-300 bg-transparent border-0 p-0 cursor-pointer"
                    >
                      Back to login
                    </button>
                  </p>
                </div>
              </form>
            ) : !isRegistering ? (
              /* Login Form */
              <form onSubmit={handleLogin}>
                <div className="mb-4">
                  <label htmlFor="email" className="block text-gray-300 mb-2">
                    Email
                  </label>
                  <input
                    type="email"
                    id="email"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="your.email@example.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <div className="mb-6">
                  <div className="flex justify-between mb-2">
                    <label htmlFor="password" className="text-gray-300">
                      Password
                    </label>
                    <button 
                      type="button"
                      onClick={handleForgotPassword}
                      className="text-sm text-blue-400 hover:text-blue-300"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <input
                    type="password"
                    id="password"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <Button
                  type="submit"
                  variant="default"
                  className="w-full"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Signing in...
                    </>
                  ) : 'Sign In'}
                </Button>

                <div className="mt-6 text-center text-gray-400">
                  <p>
                    Don't have an account?{' '}
                    <button 
                      type="button"
                      onClick={() => toggleMode('register')}
                      className="text-blue-400 hover:text-blue-300 bg-transparent border-0 p-0 cursor-pointer"
                    >
                      Create account
                    </button>
                  </p>
                </div>
              </form>
            ) : (
              /* Registration Form */
              <form onSubmit={(e) => {
                if (e.target !== e.currentTarget) return;
                handleRegister(e);
              }}>
                <div className="mb-4">
                  <label htmlFor="displayName" className="block text-gray-300 mb-2">
                    Full Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    id="displayName"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="John Smith"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <div className="mb-4">
                  <label htmlFor="registerEmail" className="block text-gray-300 mb-2">
                    Email <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="email"
                    id="registerEmail"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="your.email@example.com"
                    value={registerEmail}
                    onChange={(e) => setRegisterEmail(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                {/* Role Selection */}
                <div className="mb-4">
                  <label htmlFor="role" className="block text-gray-300 mb-2">
                    Role <span className="text-red-400">*</span>
                  </label>
                  <select
                    id="role"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    value={selectedRole}
                    onChange={(e) => setSelectedRole(e.target.value as 'technician' | 'company_admin')}
                    disabled={isLoading}
                    required
                  >
                    <option value="technician">Technician</option>
                    <option value="company_admin">Company Admin</option>
                  </select>
                  <p className="text-xs text-gray-400 mt-1">
                    {selectedRole === 'technician' ? 
                      'Field technicians need approval from their company admin' : 
                      'Company admins need approval from system administrators'}
                  </p>
                  {useDirectApproval && (
                    <div className="mt-2 p-2 border border-blue-500 bg-blue-900/20 rounded-md">
                      <p className="text-xs text-blue-300">
                        Using direct registration API for improved permissions handling
                      </p>
                    </div>
                  )}
                </div>

                {/* Company field - conditional required for company_admin */}
                <div className="mb-4">
                  <label htmlFor="company" className="block text-gray-300 mb-2">
                    Company {selectedRole === 'company_admin' ? <span className="text-red-400">*</span> : <span className="text-gray-500">(optional)</span>}
                  </label>
                  <input
                    type="text"
                    id="company"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="Company name"
                    value={company}
                    onChange={(e) => setCompany(e.target.value)}
                    disabled={isLoading}
                    required={selectedRole === 'company_admin'}
                  />
                  {selectedRole === 'company_admin' && !company && 
                    <p className="text-xs text-red-400 mt-1">Company name is required for Company Admin role</p>
                  }
                </div>

                <div className="mb-4">
                  <label htmlFor="location" className="block text-gray-300 mb-2">
                    Location <span className="text-gray-500">(optional)</span>
                  </label>
                  <input
                    type="text"
                    id="location"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="City, State, Country"
                    value={location_}
                    onChange={(e) => setLocation_(e.target.value)}
                    disabled={isLoading}
                  />
                </div>

                <div className="mb-4">
                  <label htmlFor="registerPassword" className="block text-gray-300 mb-2">
                    Password <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    id="registerPassword"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    value={registerPassword}
                    onChange={(e) => setRegisterPassword(e.target.value)}
                    disabled={isLoading}
                    required
                    minLength={6}
                  />
                </div>

                <div className="mb-6">
                  <label htmlFor="confirmPassword" className="block text-gray-300 mb-2">
                    Confirm Password <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    id="confirmPassword"
                    className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="••••••••"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    disabled={isLoading}
                    required
                  />
                </div>

                <Button
                  type="submit"
                  variant="default"
                  className="w-full"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <>
                      <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Creating account...
                    </>
                  ) : 'Create Account'}
                </Button>

                                <div className="mt-6 text-center text-gray-400">
                  <p>
                    Already have an account?{' '}
                    <button
                      type="button"
                      onClick={() => toggleMode('login')}
                      className="text-blue-400 hover:text-blue-300 bg-transparent border-0 p-0 cursor-pointer"
                    >
                      Sign in
                    </button>
                  </p>
                </div>
              </form>
            )}
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="py-4 bg-gray-800 mt-auto border-t border-gray-700">
        <div className="container mx-auto px-4 text-center text-gray-400">
          <p>&copy; 2025 JuniorTechBot. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
