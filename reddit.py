#!/usr/bin/env python3

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import praw
import prawcore
import random
import re
import threading
from PIL import Image, ImageTk

class RedditGiveawayApp:
    def __init__(self, master):
        self.master = master
        master.title("PokeLenz Giveaway Tool")
        master.geometry("1000x1000")

        # --- Load Logos ---
        try:
            self.logo_image = ImageTk.PhotoImage(Image.open("logo.png").resize((32, 32)))
            master.iconphoto(True, self.logo_image)
            self.logo_name_image = ImageTk.PhotoImage(Image.open("logo_name.png").resize((200, 50)))
        except Exception as e:
            print(f"Error loading images: {e}")
            self.logo_image = None
            self.logo_name_image = None
            messagebox.showwarning("Image Error", "Could not load logo.png or logo_name.png. Please ensure they are in the same directory as the script.")

        # --- Data ---
        self.reddit = None
        self.fetched_usernames = set()
        self.giveaway_items = []
        self.drawn_winners = []
        # Initialize StringVar for PRAW credentials
        self.client_id_var = tk.StringVar()
        self.client_secret_var = tk.StringVar()
        self.user_agent_var = tk.StringVar()

        # --- Style ---
        style = ttk.Style()
        style.configure("TButton", padding=5)
        style.configure("TLabel", padding=5)
        style.configure("TLabelframe.Label", padding=5)
        style.configure("Header.TLabel", font=("Helvetica", 16, "bold")) # Style for header

        # --- Header with Logo ---
        header_frame = ttk.Frame(master)
        header_frame.pack(pady=10)
        if self.logo_name_image:
            ttk.Label(header_frame, image=self.logo_name_image).pack()
        else:
            ttk.Label(header_frame, text="PokeLenz Giveaway Tool", style="Header.TLabel").pack()

        # --- PRAW Credentials Button ---
        self.praw_config_button = ttk.Button(master, text="Configure Reddit API", command=self._open_praw_config_dialog)
        self.praw_config_button.pack(pady=10)
        self.praw_status_label = ttk.Label(master, text="PRAW Status: Not Initialized")
        self.praw_status_label.pack()

        # --- Main Content PanedWindow ---
        main_paned_window = ttk.PanedWindow(master, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # --- Left Pane (URLs & Items) ---
        left_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(left_pane, weight=1)

        # --- Reddit URLs Frame ---
        urls_frame = ttk.Labelframe(left_pane, text="Reddit Post URLs", padding=10)
        urls_frame.pack(padx=5, pady=5, fill="both", expand=True)

        ttk.Label(urls_frame, text="Enter Reddit post URLs (one per line):").pack(anchor="w")
        self.urls_text = scrolledtext.ScrolledText(urls_frame, height=6, width=50, wrap=tk.WORD)
        self.urls_text.pack(fill="x", expand=True, pady=5)

        self.fetch_commenters_button = ttk.Button(urls_frame, text="Fetch Commenters", command=self._start_fetch_commenters_thread, state=tk.DISABLED)
        self.fetch_commenters_button.pack(pady=5)
        self.user_count_var = tk.StringVar(value="Fetched Commenters: 0")
        ttk.Label(urls_frame, textvariable=self.user_count_var).pack(pady=2)

        # --- Giveaway Items Frame ---
        items_frame = ttk.Labelframe(left_pane, text="Giveaway Items", padding=10)
        items_frame.pack(padx=5, pady=5, fill="both", expand=True)

        ttk.Label(items_frame, text="Enter giveaway items (one per line):").pack(anchor="w")
        self.items_text = scrolledtext.ScrolledText(items_frame, height=6, width=50, wrap=tk.WORD)
        self.items_text.pack(fill="x", expand=True, pady=5)

        self.load_items_button = ttk.Button(items_frame, text="Load Items", command=self._load_items)
        self.load_items_button.pack(pady=5)
        self.item_count_var = tk.StringVar(value="Items Loaded: 0")
        ttk.Label(items_frame, textvariable=self.item_count_var).pack(pady=2)

        # --- Right Pane (Action & Log) ---
        right_pane = ttk.Frame(main_paned_window, padding=5)
        main_paned_window.add(right_pane, weight=1)
        
        # --- Action & Log Frame ---
        action_log_frame = ttk.Labelframe(right_pane, text="Giveaway Control & Activity Log", padding=10)
        action_log_frame.pack(padx=5, pady=5, fill="both", expand=True)

        self.run_giveaway_button = ttk.Button(action_log_frame, text="Run Giveaway!", command=self._run_giveaway, state=tk.DISABLED)
        self.run_giveaway_button.pack(pady=10)

        ttk.Label(action_log_frame, text="Activity Log:").pack(anchor="w")
        self.activity_log_text = scrolledtext.ScrolledText(action_log_frame, height=15, width=60, wrap=tk.WORD, state=tk.DISABLED)
        self.activity_log_text.pack(fill="both", expand=True, pady=5)

        # --- Status Bar ---
        self.status_var = tk.StringVar(value="Ready. Please initialize PRAW.")
        status_bar = ttk.Label(master, textvariable=self.status_var, relief=tk.SUNKEN, anchor="w", padding=5)
        status_bar.pack(side=tk.BOTTOM, fill="x")

        self._check_enable_run_giveaway_button() # Initial check

    def _update_status(self, message):
        self.status_var.set(message)
        self.master.update_idletasks() # Ensure status updates immediately

    def _open_praw_config_dialog(self):
        self.config_window = tk.Toplevel(self.master)
        self.config_window.title("PRAW API Configuration")
        self.config_window.geometry("450x250")
        self.config_window.transient(self.master) # Keep on top of main window
        self.config_window.grab_set() # Modal behavior

        config_frame = ttk.Labelframe(self.config_window, text="Reddit API Credentials", padding=15)
        config_frame.pack(expand=True, fill="both", padx=10, pady=10)

        ttk.Label(config_frame, text="Client ID:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.dialog_client_id_var = tk.StringVar(value=self.client_id_var.get())
        ttk.Entry(config_frame, textvariable=self.dialog_client_id_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="Client Secret:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.dialog_client_secret_var = tk.StringVar(value=self.client_secret_var.get())
        ttk.Entry(config_frame, textvariable=self.dialog_client_secret_var, width=40, show="*").grid(row=1, column=1, padx=5, pady=5)

        ttk.Label(config_frame, text="User Agent:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.dialog_user_agent_var = tk.StringVar(value=self.user_agent_var.get())
        ttk.Entry(config_frame, textvariable=self.dialog_user_agent_var, width=40).grid(row=2, column=1, padx=5, pady=5)
        ttk.Label(config_frame, text="(e.g., MyApp/1.0 by YourUsername)").grid(row=2, column=2, sticky="w", padx=2, pady=5)

        init_button = ttk.Button(config_frame, text="Initialize PRAW", command=self._initialize_praw_from_dialog)
        init_button.grid(row=3, column=0, columnspan=3, pady=15)

    def _initialize_praw_from_dialog(self):
        # Persist credentials from dialog vars to main app vars
        self.client_id_var.set(self.dialog_client_id_var.get())
        self.client_secret_var.set(self.dialog_client_secret_var.get())
        self.user_agent_var.set(self.dialog_user_agent_var.get())
        
        # Close the dialog before attempting initialization
        # so messages appear on main window status
        if hasattr(self, 'config_window') and self.config_window.winfo_exists():
            self.config_window.destroy()

        self._initialize_praw()

    def _initialize_praw(self):
        client_id = self.client_id_var.get().strip()
        client_secret = self.client_secret_var.get().strip()
        user_agent = self.user_agent_var.get().strip()

        if not all([client_id, client_secret, user_agent]):
            messagebox.showerror("Error", "All PRAW credentials are required.")
            return

        self._update_status("Initializing PRAW...")
        try:
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                read_only=True # Important for script apps not needing to act as a user
            )
            # Test connection (optional, PRAW does lazy loading)
            self.reddit.user.me() # This will raise an exception if auth fails
            self._update_status("PRAW initialized successfully.")
            self.praw_status_label.config(text="PRAW Status: Initialized Successfully", foreground="green")
            messagebox.showinfo("Success", "PRAW initialized successfully!")
            self.praw_config_button.config(text="Reconfigure Reddit API") # Update button text
            self.fetch_commenters_button.config(state=tk.NORMAL)
            self._check_enable_run_giveaway_button()
        except prawcore.exceptions.OAuthException as e:
            self.reddit = None
            self._update_status(f"PRAW Initialization Failed: OAuth Error - {e}")
            self.praw_status_label.config(text="PRAW Status: OAuth Error", foreground="red")
            messagebox.showerror("PRAW Error", f"OAuth Error: {e}\nCheck your Client ID and Secret.")
            self.fetch_commenters_button.config(state=tk.DISABLED)
        except Exception as e:
            self.reddit = None
            self._update_status(f"PRAW Initialization Failed: {e}")
            self.praw_status_label.config(text=f"PRAW Status: Failed - {e}", foreground="red")
            messagebox.showerror("PRAW Error", f"Failed to initialize PRAW: {e}")
            self.fetch_commenters_button.config(state=tk.DISABLED)

    def _start_fetch_commenters_thread(self):
        if not self.reddit:
            messagebox.showerror("Error", "PRAW not initialized.")
            return

        urls_str = self.urls_text.get("1.0", tk.END).strip()
        if not urls_str:
            messagebox.showinfo("Info", "No URLs provided to fetch commenters from.")
            return

        self.fetch_commenters_button.config(state=tk.DISABLED)
        self._update_status("Starting to fetch commenters...")
        
        # Run PRAW network calls in a separate thread
        thread = threading.Thread(target=self._fetch_commenters_task, args=(urls_str,))
        thread.daemon = True # Allows main program to exit even if thread is running
        thread.start()

    def _fetch_commenters_task(self, urls_str):
        urls = [url.strip() for url in urls_str.splitlines() if url.strip()]

        current_fetched_usernames = set()
        processed_urls = 0
        total_urls = len(urls)
        self.master.after(0, self._clear_activity_log)

        for i, url_string in enumerate(urls):
            self.master.after(0, lambda msg=f"Processing URL {i+1}/{total_urls}: {url_string[:50]}...": self._update_status(msg))
            try:
                submission = self.reddit.submission(url=url_string)
                submission.comments.replace_more(limit=None)
                
                comment_count_in_post = 0
                for comment in submission.comments.list():
                    if comment.author and comment.author.name:
                        current_fetched_usernames.add(comment.author.name)
                        comment_count_in_post +=1
                
                self.master.after(0, lambda msg=f"Processed {comment_count_in_post} comments from URL {i+1}.": self._append_to_activity_log(msg))
                processed_urls += 1

            except prawcore.exceptions.Redirect: # e.g. if URL is for a subreddit, not a post
                self.master.after(0, lambda u=url_string: messagebox.showwarning("URL Error", f"Could not fetch comments. URL may not be a valid submission link: {u}"))
                self.master.after(0, lambda msg=f"Skipped invalid URL: {url_string[:50]}...": self._append_to_activity_log(msg))
            except prawcore.exceptions.NotFound:
                self.master.after(0, lambda u=url_string: messagebox.showwarning("URL Error", f"Submission not found at URL: {u}"))
                self.master.after(0, lambda msg=f"Skipped non-existent URL: {url_string[:50]}...": self._append_to_activity_log(msg))
            except Exception as e:
                self.master.after(0, lambda u=url_string, err=str(e): messagebox.showerror("Error", f"Error fetching comments from {u}: {err}"))
                self.master.after(0, lambda msg=f"Error on URL: {url_string[:50]}...": self._append_to_activity_log(msg))

        self.master.after(0, self._finalize_fetch_commenters, current_fetched_usernames, processed_urls, total_urls)

    def _finalize_fetch_commenters(self, new_usernames, processed_urls, total_urls):
        self.fetched_usernames.update(new_usernames)
        self.user_count_var.set(f"Fetched Commenters: {len(self.fetched_usernames)}")
        
        if processed_urls == total_urls and total_urls > 0:
            self._update_status(f"Finished fetching. Total unique commenters: {len(self.fetched_usernames)} from {processed_urls} URL(s).")
            messagebox.showinfo("Fetch Complete", f"Fetched {len(self.fetched_usernames)} unique commenters from {processed_urls} URL(s).")
        elif total_urls == 0:
             self._update_status("No URLs provided.")
        else:
            self._update_status(f"Partially completed fetching. Total unique commenters: {len(self.fetched_usernames)}. Processed {processed_urls}/{total_urls} URLs.")
            messagebox.showwarning("Fetch Incomplete", f"Processed {processed_urls} out of {total_urls} URLs. Check console or status for errors.")

        self.fetch_commenters_button.config(state=tk.NORMAL)
        self._check_enable_run_giveaway_button()

    def _clear_activity_log(self):
        self.activity_log_text.config(state=tk.NORMAL)
        self.activity_log_text.delete('1.0', tk.END)
        self.activity_log_text.config(state=tk.DISABLED)

    def _append_to_activity_log(self, message):
        """Helper to show transient messages in the activity log"""
        self.activity_log_text.config(state=tk.NORMAL)
        self.activity_log_text.insert(tk.END, message + "\n")
        self.activity_log_text.see(tk.END) # Scroll to the end
        self.activity_log_text.config(state=tk.DISABLED)

    def _load_items(self):
        items_str = self.items_text.get("1.0", tk.END).strip()
        if not items_str:
            self.giveaway_items = []
            self.item_count_var.set("Items Loaded: 0")
            self._update_status("No items loaded.")
            messagebox.showinfo("Info", "No items entered.")
            self._check_enable_run_giveaway_button()
            return

        self.giveaway_items = [item.strip() for item in items_str.splitlines() if item.strip()]
        self.item_count_var.set(f"Items Loaded: {len(self.giveaway_items)}")
        self._update_status(f"Loaded {len(self.giveaway_items)} giveaway items.")
        self._check_enable_run_giveaway_button()
        messagebox.showinfo("Items Loaded", f"{len(self.giveaway_items)} items loaded successfully.")

    def _check_enable_run_giveaway_button(self):
        if self.reddit and self.fetched_usernames and self.giveaway_items:
            self.run_giveaway_button.config(state=tk.NORMAL)
        else:
            self.run_giveaway_button.config(state=tk.DISABLED)

    def _run_giveaway(self):
        self._update_status("Running giveaway...")
        if not self.fetched_usernames:
            messagebox.showerror("Error", "No commenters fetched. Please fetch commenters first.")
            self._update_status("Error: No commenters available for giveaway.")
            return
        if not self.giveaway_items:
            messagebox.showerror("Error", "No giveaway items loaded. Please load items first.")
            self._update_status("Error: No items available for giveaway.")
            return

        available_users = list(self.fetched_usernames)
        available_items = list(self.giveaway_items)

        random.shuffle(available_users)
        random.shuffle(available_items)

        self.drawn_winners = []
        num_possible_winners = min(len(available_users), len(available_items))

        for i in range(num_possible_winners):
            winner = available_users.pop()
            prize = available_items.pop()
            self.drawn_winners.append((winner, prize))

        self._show_giveaway_results_window()
        
        final_status = f"Giveaway complete! {len(self.drawn_winners)} winner(s) drawn."
        if len(available_users) > 0 and num_possible_winners > 0 :
             final_status += f" {len(available_users)} users did not win an item."
        if len(available_items) > 0 and num_possible_winners > 0:
             final_status += f" {len(available_items)} items were not awarded."
        self._update_status(final_status)
        messagebox.showinfo("Giveaway Complete", f"{len(self.drawn_winners)} winner(s) drawn!")

    def _show_giveaway_results_window(self):
        results_window = tk.Toplevel(self.master)
        results_window.title("🎉 Giveaway Results! 🎉")
        results_window.geometry("600x700") # Increased size
        results_window.transient(self.master)
        results_window.grab_set()

        if self.logo_image: # Use the small logo as window icon for results too
            results_window.iconphoto(True, self.logo_image)

        main_frame = ttk.Frame(results_window, padding=20)
        main_frame.pack(expand=True, fill="both")

        ttk.Label(main_frame, text="Congratulations to the Winners!", font=("Helvetica", 20, "bold"), foreground="purple").pack(pady=20)

        results_text_area = scrolledtext.ScrolledText(main_frame, height=15, width=70, wrap=tk.WORD, font=("Helvetica", 11))
        results_text_area.pack(fill="both", expand=True, pady=10)
        results_text_area.insert(tk.END, "--- 🏆 Giveaway Winners 🏆 ---\n\n")

        self.winners_to_display = list(self.drawn_winners) 
        self.current_winner_index = 0

        def display_next_winner(text_widget, winners_list):
            if self.current_winner_index < len(winners_list):
                user, item = winners_list[self.current_winner_index]
                text_widget.insert(tk.END, f"✨ Winner {self.current_winner_index + 1}: {user} wins \"{item}\" ✨\n\n")
                text_widget.see(tk.END)
                self.current_winner_index += 1
                results_window.after(750, lambda: display_next_winner(text_widget, winners_list)) 
            else:

                remaining_items_count = len(self.giveaway_items) - len(self.drawn_winners)

                if remaining_items_count > 0 and len(self.fetched_usernames) < len(self.giveaway_items):
                    text_widget.insert(tk.END, f"\n--- {remaining_items_count} item(s) not awarded (no more unique users) ---\n")
                
                text_widget.config(state=tk.DISABLED)

                close_button = ttk.Button(main_frame, text="Close", command=results_window.destroy)
                close_button.pack(pady=20)
                
        if not self.drawn_winners:
            results_text_area.insert(tk.END, "No winners drawn. Check if users and items were available.\n")
            results_text_area.config(state=tk.DISABLED)
            close_button = ttk.Button(main_frame, text="Close", command=results_window.destroy)
            close_button.pack(pady=20)
        else:
            results_text_area.config(state=tk.NORMAL) # Enable for inserting
            display_next_winner(results_text_area, self.winners_to_display) # Start animation


if __name__ == "__main__":
    root = tk.Tk()
    app = RedditGiveawayApp(root)
    root.mainloop()
