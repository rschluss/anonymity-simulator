#
#  extended_rounds.py
#  
#
#  Created by Rebecca Schlussel on 4/17/13.
#  Copyright (c) 2013 __MyCompanyName__. All rights reserved.
#

class Round_Keeper:	
  def __init__ (self):
    
    #initialize group_round_keepers with the "round_keeper" for the 
    #ungrouped messages
    self.group_round_keepers = [Round_Keeper.Group_Round_Keeper([])]	

  def add_group(self,group,online_group):
    self.group_round_keepers.insert(-1,\
                    Round_Keeper.Group_Round_Keeper(online_group))
    #add any ungrouped messages belonging to the group
    for message in self.get_messages_for_group(-1)[:]:
      if message[2][0] in group: 
        self.remove_message_from_group(message,-1)
        self.add_message_to_group(-2,uid,message) 
  
  def add_online_member_to_group(self,member,gid):
    self.group_round_keepers[gid].add_online_member(member)
	
  def remove_offline_member_from_group(self,member,gid):
    self.group_round_keepers[gid].remove_offline_member(member)
  
  def get_num_online_members_for_group(self,gid):
    return len(self.group_round_keepers[gid].online_members)
  
  def get_num_round_members_for_group(self,gid):
    return len(self.group_round_keepers[gid].round_members)

  def add_message_to_group(self,gid,uid,message):
    if gid == -1 or gid == len(self.group_round_keepers): 
      self.group_round_keepers[gid].messages.append(message)
    else:	
      self.group_round_keepers[gid].add_message(uid,message)
  
  def remove_message_from_group(self,message,gid):
    self.group_round_keepers[gid].remove_message(message)
    
  def get_messages_for_group(self,gid):
    return self.group_round_keepers[gid].messages  

  def end_group_round(self,gid):
    group_round_keeper = self.group_round_keepers[gid]	
    group_round_keeper.end_group_round()
  
  def end_global_round_for_group(self,gid):
    self.group_round_keepers[gid].end_global_round()
  
  def get_all_round_messages(self):
    messages = []
    for group_round_keeper in self.group_round_keepers:
      messages.extend(group_round_keeper.messages)
    return messages

  def get_next_round_messages(self):
    messages = []
    for group_round_keeper in self.group_round_keepers:
        messages.extend(group_round_keeper.next_messages)
    return messages	
	
  class Group_Round_Keeper:
    def __init__(self, online_group):
      self.online_members = online_group
      self.round_members = online_group
      self.new_round_members = online_group
      self.messages = []
      self.next_messages = []
	
    def add_online_member(self,member):
      if member not in self.online_members:
        self.online_members.append(member)
      if member not in self.new_round_members:
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
      self.round_members = self.online_members
      self.new_round_members = self.online_members
      self.messages.extend(self.next_messages)
      self.next_messages = []
          
			
