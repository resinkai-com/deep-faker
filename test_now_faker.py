#!/usr/bin/env python3
"""Test script to verify 'now' faker functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from datetime import datetime, timedelta
from deep_faker import (
    BaseEvent, Context, Field, NewEvent, Simulation, Entity, StateField
)

# Event schema using 'now' faker
class UserRegistered(BaseEvent):
    user_id: str = Field(primary_key=True, faker="uuid4")
    full_name: str = Field(faker="name")
    email: str = Field(faker="email")
    registered_at: datetime = Field(faker="now")  # Should use simulation time

class UserEntity(Entity):
    source_event = UserRegistered
    primary_key = "user_id"

def test_now_faker():
    """Test that 'now' faker uses simulation time correctly."""
    
    # Create simulation with specific start time
    start_time = datetime(2024, 1, 1, 12, 0, 0)
    sim = Simulation(
        duration="30s",
        start_time=start_time,
        random_seed=123
    )
    
    # Capture events
    captured_events = []
    
    class TestOutput:
        def send_event(self, event):
            captured_events.append(event)
        def close(self):
            pass
            
    sim.add_output(TestOutput())
    
    # Create a flow that generates events at different simulation times
    @sim.flow(initiation_weight=10.0)
    def time_sensitive_flow(ctx: Context):
        """Generate events with 'now' faker at different times."""
        # First event at initial time
        yield NewEvent(ctx, UserRegistered, save_entity=UserEntity)
        
        # Advance time by 10 seconds
        from deep_faker import AddDecay
        yield AddDecay(ctx, rate=0.0, seconds=10)  # 0% chance to terminate
        
        # Second event 10 seconds later
        yield NewEvent(ctx, UserRegistered, save_entity=UserEntity)
        
        # Advance time by another 5 seconds
        yield AddDecay(ctx, rate=0.0, seconds=5)
        
        # Third event 15 seconds after start
        yield NewEvent(ctx, UserRegistered, save_entity=UserEntity)
    
    # Run simulation
    sim.run()
    
    print(f"\nGenerated {len(captured_events)} events")
    
    # Verify that registered_at times match simulation progression
    times = []
    for i, event in enumerate(captured_events):
        if hasattr(event, 'registered_at'):
            reg_time = event.registered_at
            times.append(reg_time)
            print(f"Event {i+1}: registered_at = {reg_time}")
            
            # Verify it's a datetime object
            assert isinstance(reg_time, datetime), f"registered_at should be datetime, got {type(reg_time)}"
        else:
            print(f"Event {i+1}: No registered_at field found")
    
    # Should have at least some events with times
    assert len(times) > 0, "Should have events with registered_at field"
    
    # If we have multiple events, verify time progression makes sense
    if len(times) > 1:
        print(f"\nTime differences:")
        unique_times = sorted(set(times))
        print(f"Unique times: {unique_times}")
        
        # Should have some time progression (events at different times)
        assert len(unique_times) > 1, "Should have events at different simulation times"
        
        # All times should be >= start time
        for t in times:
            assert t >= start_time, f"Event time {t} should be >= start time {start_time}"
    
    # Also verify the events contain expected simulation start time
    if times:
        first_time = times[0]
        # Should be close to our start time (within a few seconds due to simulation overhead)
        time_diff = abs((first_time - start_time).total_seconds())
        print(f"First event time vs start time diff: {time_diff} seconds")
        assert time_diff < 5, f"First event time should be close to start time, diff: {time_diff}s"
    
    print("\n'now' faker test completed successfully!")

if __name__ == "__main__":
    test_now_faker()