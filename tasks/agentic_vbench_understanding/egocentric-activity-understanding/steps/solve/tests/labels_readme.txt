This is the action annotation for GTEA Gaze Plus dataset. The dataset contains 37 videos with action annotations and gaze tracking. Videos and gaze data should be downloaded separately from our website. 

We create a separate txt file as action labels for each video. Each line within the file defines an action. The annotation is done at 24Hz for the original videos. The format is defined as follows
<verb><noun1, noun2, ...>(starting_frame-ending_frame)

The starting/ending frame number follows 24 fps as the original video (the first frame is 0).

NOTE: In our CVPR 2015 paper, we did the following modification for benchmark.
* Spoon/Fork/spoonForkKnife is combined into a single object (spoonForkKnife) in action labels
* Bowl/Plate/Cup is combined into a single object (cupPlateBowl) in action labels
* We have revised our annotations since our CVPR'15 paper. For a fair comparison, we list the 44 action classes used in the paper (full list below)


open_fridge                      
close_fridge                     
put_cupPlateBowl                 
put_spoonForkKnife_cupPlateBowl           
take_spoonForkKnife_cupPlateBowl          
take_cupPlateBowl                
take_spoonForkKnife                       
put_lettuce_cupPlateBowl         
read_recipe                      
take_plastic_spatula             
open_freezer                     
close_freezer                    
put_plastic_spatula              
cut_tomato_spoonForkKnife                 
put_spoonForkKnife                        
take_tomato_cupPlateBowl         
turn on_tap                      
turn off_tap                     
take_cupPlateBowl_plate_container
turn off_burner                  
turn on_burner                   
cut_pepper_spoonForkKnife                 
put_tomato_cupPlateBowl          
put_milk_container               
put_oil_container                
take_oil_container               
close_oil_container              
open_oil_container               
take_lettuce_container           
take_milk_container              
open_fridge_drawer               
put_lettuce_container            
close_fridge_drawer              
compress_sandwich                
pour_oil_oil_container_skillet   
take_bread_bread_container       
cut_mushroom_spoonForkKnife               
put_bread_cupPlateBowl           
put_honey_container              
take_honey_container             
open_microwave                   
crack_egg_cupPlateBowl           
open_bread_container             
open_honey_container 


Contact: Yin Li, yli440@gatech.edu
Last update: Jan 22th, 2015
