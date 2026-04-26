import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button } from "../components/Button";
import { JuniorTechBotLogo } from "../components/JuniorTechBotLogo";
import { firebaseApp, firebaseAuth } from "../app";
import { createUserWithEmailAndPassword, updateProfile } from 'firebase/auth';
import { getFirestore, doc, setDoc, collection, Timestamp } from 'firebase/firestore';
import { COLLECTIONS, User, PendingRequest } from "../utils/firestore-schema";
import { toast } from 'sonner';

export default function Register() {
  const navigate = useNavigate();
  
  const [displayName, setDisplayName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [company, setCompany] = useState('');
  const [location, setLocation] = useState('');
  const [role, setRole] = useState<'technician' | 'company_admin'>('technician');
  const [organization, setOrganization] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  
  const firestore = getFirestore(firebaseApp);
  
  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Basic form validation
    if (!displayName.trim()) {
      setFormError('Name is required');
      return;
    }
    
    if (!email.trim()) {
      setFormError('Email is required');
      return;
    }
    
    if (password.length < 6) {
      setFormError('Password must be at least 6 characters');
      return;
    }
    
    if (password !== confirmPassword) {
      setFormError('Passwords do not match');
      return;
    }
    
    // Company is required for company admins
    if (role === 'company_admin' && !company.trim()) {
      setFormError('Company name is required for Company Admin role');
      return;
    }
    
    try {
      setIsLoading(true);
      setFormError(null);
      
      // 1. Create Firebase Auth account
      const userCredential = await createUserWithEmailAndPassword(
        firebaseAuth, 
        email, 
        password
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
        role: role,
        approvalStatus: 'pending_approval',
        createdAt: now,
        lastActive: now,
      };
      
      // Add optional fields if provided
      if (company.trim()) {
        userProfile.company = company.trim();
      }

      if (organization.trim()) {
        userProfile.organization = organization.trim();
      }
      // Store location in a custom field (not in the User interface)
      // This could be stored in a separate collection or used when implementing
      // a profile update feature in the future
      
      // Save profile to Firestore
      await setDoc(doc(firestore, COLLECTIONS.USERS, user.uid), userProfile);
      
      // Create a pending request for approval
      const pendingRequest: PendingRequest = {
        id: user.uid,
        uid: user.uid,
        userEmail: user.email!,
        displayName: displayName,
        requestedRole: role,
        company: company.trim() || null,
        organization: organization.trim() || null, // <-- ADD THIS LINE
        requestedAt: now,
        status: 'pending',
      };
      
      // Save pending request to Firestore
      await setDoc(doc(firestore, COLLECTIONS.PENDING_REQUESTS, user.uid), pendingRequest);
      
      // Show success toast
      toast.success('Account created successfully! Your account is pending approval.');
      
      // Redirect to home
      navigate('');
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
                <Link to="" className="text-gray-300 hover:text-white">
                  Home
                </Link>
              </li>
              <li>
                <Link to="Login" className="text-gray-300 hover:text-white">
                  Login
                </Link>
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
              <h2 className="text-2xl font-bold">Create your account</h2>
              <p className="text-gray-400 mt-2">Join JuniorTechBot to get started</p>
            </div>
            
            <form onSubmit={handleRegister}>
              {formError && (
                <div className="mb-4 p-3 bg-red-900/30 border border-red-700 rounded-md text-red-400 text-sm">
                  {formError}
                </div>
              )}
              
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
                <label htmlFor="email" className="block text-gray-300 mb-2">
                  Email <span className="text-red-400">*</span>
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
              
              {/* Optional fields */}
              <div className="mb-4">
                <label htmlFor="company" className="block text-gray-300 mb-2">
                  Company {role === 'company_admin' && <span className="text-red-400">*</span>}
                  {role === 'technician' && <span className="text-gray-500">(optional)</span>}
                </label>
                <input
                  type="text"
                  id="company"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Company name"
                  value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  disabled={isLoading}
                  required={role === 'company_admin'}
                />
              </div>

              {/* Organization Field */}
              <div className="mb-4">
                <label htmlFor="organization" className="block text-gray-300 mb-2">
                  Organization <span className="text-gray-500">(optional)</span>
                </label>
                <input
                  type="text"
                  id="organization"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Department or Team Name"
                  value={organization}
                  onChange={(e) => setOrganization(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              
              <div className="mb-4">
                <label htmlFor="role" className="block text-gray-300 mb-2">
                  Role <span className="text-red-400">*</span>
                </label>
                <div className="grid grid-cols-2 gap-4">
                  <div
                    className={`flex items-center p-3 ${role === 'technician' ? 'bg-blue-900/30 border-blue-600' : 'bg-gray-700'} border rounded-md cursor-pointer hover:bg-gray-600`}
                    onClick={() => setRole('technician')}
                  >
                    <div className="flex-shrink-0 mr-3">
                      <div className={`w-5 h-5 rounded-full border ${role === 'technician' ? 'border-blue-500' : 'border-gray-500'} flex items-center justify-center`}>
                        {role === 'technician' && (
                          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="font-medium">Technician</p>
                      <p className="text-xs text-gray-400">Field service role</p>
                    </div>
                  </div>
                  
                  <div
                    className={`flex items-center p-3 ${role === 'company_admin' ? 'bg-blue-900/30 border-blue-600' : 'bg-gray-700'} border rounded-md cursor-pointer hover:bg-gray-600`}
                    onClick={() => setRole('company_admin')}
                  >
                    <div className="flex-shrink-0 mr-3">
                      <div className={`w-5 h-5 rounded-full border ${role === 'company_admin' ? 'border-blue-500' : 'border-gray-500'} flex items-center justify-center`}>
                        {role === 'company_admin' && (
                          <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                        )}
                      </div>
                    </div>
                    <div>
                      <p className="font-medium">Company Admin</p>
                      <p className="text-xs text-gray-400">Management role</p>
                    </div>
                  </div>
                </div>
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
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={isLoading}
                />
              </div>
              
              <div className="mb-4">
                <label htmlFor="password" className="block text-gray-300 mb-2">
                  Password <span className="text-red-400">*</span>
                </label>
                <input
                  type="password"
                  id="password"
                  className="w-full px-4 py-2 bg-gray-700 border border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
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
                  <Link to="Login" className="text-blue-400 hover:text-blue-300">
                    Sign in
                  </Link>
                </p>
              </div>
            </form>
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
