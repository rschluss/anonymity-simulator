#
#  extended_rounds.py
#  
#
#  Created by Rebecca Schlussel on 4/17/13.
#  Copyright (c) 2013 __MyCompanyName__. All rights reserved.
#

class Round_Keeper:	
	def __init__ (self):
		self.total_wait_time = 0
		self.total_delayed_messages = 0
		group_round_keepers = []	
	
	def add_group(self,online_group):
		self.group_round_keepers.append(Group_Round_Keeper(online_group))
	
	def add_online_member_to_group(self,member,gid):
		self.group_round_keepers[gid].add_online_member(member)
	
	def remove_offline_member_from_group(self,member,gid):
		self.group_round_keepers[gid].remove_offline_member(member)
  
  def get_num_online_members_for_group(gid):
    len(self.group_round_keeper[gid].online_members)
  
  def add_message_to_group(gid,uid,message):
    self.group_round_keepers[gid].add_message(uid,message)
	
  def remove_message_from_group(gid,message)
    self.group_round_keepers[gid].remove_message(message)
    
	def end_group_round(self,gid):
		group_round_keeper = self.group_round_keepers[gid]
		
		self.total_delayed_messages += group_round_keeper.messages 		
		self.total_wait_time += group_round_keeper.wait_time
		
		self.group_round_keepesr.end_group_round()
  
  def end_global_round(self):
    for group_round_keeper in self.group_round_keepers:
      group_round_keeper.end_global_round()
  
  def get_all_round_messages(self):
    messages = []
    for group_round_keeper in self.group_round_keepers:
      messages.extend(group_round_keeper.messages)
    return messages
		
	
  class Group_Round_Keeper:
		def __init__(self, online_group):
			self.online_members = online_group
			self.round_members = online_group
      self.new_round_members = online_group
      self.messages = []
      self.next_messages = []
	
		def add_online_member(self,member):
      self.online_members.append(member)
      if member not in self.new_round_members
        self.new_round_members.append(member)
      if member not in self.round_members:
        self.round_members.append(member)
		
		def remove_offline_member (self,member):
			self.online_members.remove(member)
			
		def add_message(self,uid,event):
      if (uid in self.new_round_members):
        self.messages.append(event)
      else:
        self.next_messages.append(event)
    
    def remove_message(self,message):
      self.messages.remove(message)
        
    def end_global_round(self):
      self.new_round_members = []

    def end_group_round(self):
      self.round_members = online_members
      self.new_round_members = online_members
      self.messages.extend(next_messages)
      self.next_messages = []
          


			